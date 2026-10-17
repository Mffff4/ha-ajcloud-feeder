"""Number platform for AJCloud Pet Feeder portions."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import AJCloudDataCoordinator
from .api import AJCloudApiClient
from .const import DEFAULT_PORTIONS, DOMAIN, MAX_PORTIONS, MIN_PORTIONS
from .device import get_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AJCloud feeder number entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    client: AJCloudApiClient = entry_data["client"]
    coordinator: AJCloudDataCoordinator = entry_data["coordinator"]

    entities = [
        AJCloudPortionsNumber(coordinator, client, entry.entry_id, device_id, dev_info)
        for device_id, dev_info in client.devices.items()
    ]
    async_add_entities(entities)


class AJCloudPortionsNumber(CoordinatorEntity[AJCloudDataCoordinator], NumberEntity):
    """Entity to choose how many portions to dispense."""

    _attr_has_entity_name = True
    _attr_translation_key = "portions"
    _attr_icon = "mdi:bowl-mix"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = MIN_PORTIONS
    _attr_native_max_value = MAX_PORTIONS
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "порц."

    def __init__(
        self,
        coordinator: AJCloudDataCoordinator,
        client: AJCloudApiClient,
        entry_id: str,
        device_id: str,
        device_raw: dict[str, Any],
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._client = client
        self._entry_id = entry_id
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_portions"
        self._attr_name = "Размер порции"
        self._attr_native_value = DEFAULT_PORTIONS
        self._attr_device_info = get_device_info(
            device_id, device_raw, coordinator.data.get(device_id)
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        int_val = int(value)
        self._attr_native_value = int_val
        self.hass.data[DOMAIN][self._entry_id]["portions"][self._device_id] = int_val
        self.async_write_ha_state()
