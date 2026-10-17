"""Button platform for AJCloud Pet Feeder."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import AJCloudDataCoordinator
from .api import AJCloudApiClient
from .const import DEFAULT_PORTIONS, DOMAIN
from .device import get_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AJCloud feeder buttons."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    client: AJCloudApiClient = entry_data["client"]
    coordinator: AJCloudDataCoordinator = entry_data["coordinator"]

    entities: list[ButtonEntity] = []
    for device_id, dev_info in client.devices.items():
        entities.append(AJCloudFeedButton(coordinator, client, entry.entry_id, device_id, dev_info))
        entities.append(AJCloudRebootButton(coordinator, client, device_id, dev_info))
    async_add_entities(entities)


class AJCloudFeedButton(CoordinatorEntity[AJCloudDataCoordinator], ButtonEntity):
    """Button to dispense pet food."""

    _attr_has_entity_name = True
    _attr_translation_key = "feed"
    _attr_icon = "mdi:food-drumstick"

    def __init__(
        self,
        coordinator: AJCloudDataCoordinator,
        client: AJCloudApiClient,
        entry_id: str,
        device_id: str,
        device_raw: dict[str, Any],
    ) -> None:
        """Initialize button."""
        super().__init__(coordinator)
        self._client = client
        self._entry_id = entry_id
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_feed_button"
        self._attr_name = "Выдать корм"
        self._attr_device_info = get_device_info(
            device_id, device_raw, coordinator.data.get(device_id)
        )

    async def async_press(self) -> None:
        """Handle button press."""
        portions_map = self.hass.data[DOMAIN][self._entry_id].get("portions", {})
        portions = portions_map.get(self._device_id, DEFAULT_PORTIONS)
        _LOGGER.info("Dispensing %d portion(s) on feeder %s", portions, self._device_id)
        await self._client.async_feed(self._device_id, portions=portions)
        self.coordinator.record_feed(self._device_id, portions)


class AJCloudRebootButton(CoordinatorEntity[AJCloudDataCoordinator], ButtonEntity):
    """Diagnostic button to reboot device."""

    _attr_has_entity_name = True
    _attr_translation_key = "reboot"
    _attr_icon = "mdi:restart"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: AJCloudDataCoordinator,
        client: AJCloudApiClient,
        device_id: str,
        device_raw: dict[str, Any],
    ) -> None:
        """Initialize reboot button."""
        super().__init__(coordinator)
        self._client = client
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_reboot_button"
        self._attr_name = "Перезагрузка кормушки"
        self._attr_device_info = get_device_info(
            device_id, device_raw, coordinator.data.get(device_id)
        )

    async def async_press(self) -> None:
        """Send reboot signal."""
        gw = self._client.gateways.get(self._device_id, "https://cam-gw-us.ajcloud.net/api")
        url = f"{gw.rstrip('/')}/v1/reboot"
        body_str = "{}"
        headers = self._client._build_signed_headers(url, body_str)
        try:
            async with self._client._session.post(url, data=body_str, headers=headers, timeout=10) as resp:
                _LOGGER.info("Reboot sent to %s (HTTP %s)", self._device_id, resp.status)
        except Exception as e:
            _LOGGER.warning("Reboot request error: %s", e)
