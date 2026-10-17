"""Camera platform for AJCloud Pet Feeder."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import AJCloudDataCoordinator
from .api import AJCloudApiClient
from .const import DOMAIN
from .device import get_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AJCloud feeder camera."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    client: AJCloudApiClient = entry_data["client"]
    coordinator: AJCloudDataCoordinator = entry_data["coordinator"]

    entities = [
        AJCloudCamera(coordinator, client, device_id, dev_info)
        for device_id, dev_info in client.devices.items()
    ]
    async_add_entities(entities)


class AJCloudCamera(CoordinatorEntity[AJCloudDataCoordinator], Camera):
    """Camera entity for the pet feeder built-in camera."""

    _attr_has_entity_name = True
    _attr_translation_key = "camera"
    _attr_icon = "mdi:cctv"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        coordinator: AJCloudDataCoordinator,
        client: AJCloudApiClient,
        device_id: str,
        device_raw: dict[str, Any],
    ) -> None:
        """Initialize camera."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._client = client
        self._device_id = device_id
        self._device_raw = device_raw
        self._attr_unique_id = f"{device_id}_camera"
        self._attr_name = "Камера"
        self._attr_device_info = get_device_info(
            device_id, device_raw, coordinator.data.get(device_id)
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        # Proactively ensure device RTSP server is active on startup
        try:
            await self._client.async_enable_rtsp(self._device_id, enable=True, port=554, verify=0)
        except Exception as err:
            _LOGGER.debug("Could not auto-enable RTSP on startup: %s", err)

    @property
    def is_recording(self) -> bool:
        """Return true if the camera is recording."""
        return False

    @property
    def is_streaming(self) -> bool:
        """Return true if camera stream is active."""
        return True

    @property
    def is_on(self) -> bool:
        """Return true if camera is on."""
        return True

    async def stream_source(self) -> str | None:
        """Return dynamic RTSP stream source for Home Assistant stream component."""
        data = self.coordinator.data.get(self._device_id, {})

        # Auto-enable RTSP server on device if not yet active
        rtsp_cfg = data.get("rtspConfig", {})
        if str(rtsp_cfg.get("enable")) not in ("1", 1, True):
            _LOGGER.debug("RTSP disabled or unverified on %s; enabling...", self._device_id)
            try:
                await self._client.async_enable_rtsp(self._device_id, enable=True, port=554, verify=0)
            except Exception as err:
                _LOGGER.warning("Could not auto-enable RTSP: %s", err)

        # 1. Prefer exact live stream URL reported by device firmware
        streams = data.get("streamConfig", {}).get("streams", [])
        if streams:
            for s in streams:
                url = s.get("localUrl")
                if url and "0.0.0.0" not in url:
                    return url

        # 2. Dynamic fallback using IP reported by device networkConfig or device_raw
        net = data.get("networkConfig", {})
        ip = (
            net.get("localIp")
            or net.get("ip")
            or data.get("localIp")
            or data.get("ip")
            or self._device_raw.get("localIp")
            or self._device_raw.get("ip")
            or self._device_raw.get("lanIp")
        )
        port = data.get("rtspConfig", {}).get("port") or 554

        if ip:
            return f"rtsp://{ip}:{port}/live/ch0"

        _LOGGER.warning("Could not determine local IP for feeder %s RTSP stream", self._device_id)
        return None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the camera."""
        data = self.coordinator.data.get(self._device_id, {})
        snapshot_url = data.get("base", {}).get("snapshotUrl")
        if snapshot_url:
            try:
                async with self._client._session.get(snapshot_url, timeout=10) as resp:
                    if resp.status == 200:
                        return await resp.read()
            except Exception as err:
                _LOGGER.debug("Could not fetch camera snapshot: %s", err)

        # Fallback to generating frame from RTSP stream via Home Assistant's stream/ffmpeg
        return await super().async_camera_image(width, height)
