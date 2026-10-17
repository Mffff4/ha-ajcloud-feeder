"""Switch platform for AJCloud Pet Feeder RTSP streaming."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
    """Set up the AJCloud feeder switch entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    client: AJCloudApiClient = entry_data["client"]
    coordinator: AJCloudDataCoordinator = entry_data["coordinator"]

    entities = [
        AJCloudRtspSwitch(coordinator, client, device_id, dev_info)
        for device_id, dev_info in client.devices.items()
    ]
    async_add_entities(entities)


class AJCloudRtspSwitch(CoordinatorEntity[AJCloudDataCoordinator], SwitchEntity):
    """Switch to enable or disable local RTSP video stream."""

    _attr_has_entity_name = True
    _attr_translation_key = "rtsp_stream"
    _attr_icon = "mdi:video-wireless"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: AJCloudDataCoordinator,
        client: AJCloudApiClient,
        device_id: str,
        device_raw: dict[str, Any],
    ) -> None:
        """Initialize RTSP switch."""
        super().__init__(coordinator)
        self._client = client
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_rtsp_switch"
        self._attr_name = "Локальный RTSP видеопоток"
        self._attr_device_info = get_device_info(
            device_id, device_raw, coordinator.data.get(device_id)
        )

    @property
    def is_on(self) -> bool:
        """Return true if RTSP stream is enabled on the device."""
        data = self.coordinator.data.get(self._device_id, {})
        cfg = data.get("rtspConfig", {})
        return str(cfg.get("enable")) in ("1", 1, True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on RTSP stream."""
        _LOGGER.info("Enabling RTSP stream on %s", self._device_id)
        await self._client.async_enable_rtsp(self._device_id, enable=True, port=554, verify=0)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off RTSP stream."""
        _LOGGER.info("Disabling RTSP stream on %s", self._device_id)
        await self._client.async_enable_rtsp(self._device_id, enable=False, port=554, verify=0)
        await self.coordinator.async_request_refresh()
