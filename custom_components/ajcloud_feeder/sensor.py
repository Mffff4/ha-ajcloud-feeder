"""Sensor platform for AJCloud Pet Feeder."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import AJCloudDataCoordinator
from .api import AJCloudApiClient
from .const import DOMAIN
from .device import get_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AJCloud feeder sensors."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    client: AJCloudApiClient = entry_data["client"]
    coordinator: AJCloudDataCoordinator = entry_data["coordinator"]

    entities: list[SensorEntity] = []
    for device_id, dev_info in client.devices.items():
        entities.extend([
            AJCloudStatusSensor(coordinator, device_id, dev_info),
            AJCloudLastFeedSensor(coordinator, device_id, dev_info),
            AJCloudPortionsTodaySensor(coordinator, device_id, dev_info),
            AJCloudWifiSensor(coordinator, device_id, dev_info),
            AJCloudFirmwareSensor(coordinator, device_id, dev_info),
            AJCloudIpSensor(coordinator, device_id, dev_info),
        ])
    async_add_entities(entities)


class AJCloudBaseSensor(CoordinatorEntity[AJCloudDataCoordinator], SensorEntity):
    """Base sensor for AJCloud."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AJCloudDataCoordinator,
        device_id: str,
        device_raw: dict[str, Any],
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_device_info = get_device_info(
            device_id, device_raw, coordinator.data.get(device_id)
        )


class AJCloudStatusSensor(AJCloudBaseSensor):
    """Connection status sensor."""

    _attr_icon = "mdi:check-network-outline"

    def __init__(self, coordinator: AJCloudDataCoordinator, device_id: str, device_raw: dict[str, Any]) -> None:
        super().__init__(coordinator, device_id, device_raw)
        self._attr_unique_id = f"{device_id}_status"
        self._attr_name = "Статус подключения"

    @property
    def native_value(self) -> str:
        data = self.coordinator.data.get(self._device_id, {})
        base = data.get("base", {})
        status = base.get("onlineStatus")
        if status in (1, 2, "1", "2"):
            return "В сети"
        return "Не в сети"


class AJCloudLastFeedSensor(AJCloudBaseSensor):
    """Timestamp of last food dispensing."""

    _attr_icon = "mdi:clock-check-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: AJCloudDataCoordinator, device_id: str, device_raw: dict[str, Any]) -> None:
        super().__init__(coordinator, device_id, device_raw)
        self._attr_unique_id = f"{device_id}_last_feed"
        self._attr_name = "Последнее кормление"

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_feed_time.get(self._device_id)


class AJCloudPortionsTodaySensor(AJCloudBaseSensor):
    """Total portions dispensed today."""

    _attr_icon = "mdi:bowl-mix-outline"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "порц."

    def __init__(self, coordinator: AJCloudDataCoordinator, device_id: str, device_raw: dict[str, Any]) -> None:
        super().__init__(coordinator, device_id, device_raw)
        self._attr_unique_id = f"{device_id}_portions_today"
        self._attr_name = "Выдано сегодня"

    @property
    def native_value(self) -> int:
        return self.coordinator.portions_today.get(self._device_id, 0)


class AJCloudWifiSensor(AJCloudBaseSensor):
    """Wi-Fi signal strength sensor."""

    _attr_icon = "mdi:wifi"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AJCloudDataCoordinator, device_id: str, device_raw: dict[str, Any]) -> None:
        super().__init__(coordinator, device_id, device_raw)
        self._attr_unique_id = f"{device_id}_wifi"
        self._attr_name = "Уровень сигнала Wi-Fi"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data.get(self._device_id, {})
        sig = data.get("wifiSignal") or data.get("base", {}).get("wifiSignal")
        return int(sig) if sig is not None else 85


class AJCloudFirmwareSensor(AJCloudBaseSensor):
    """Firmware version sensor."""

    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AJCloudDataCoordinator, device_id: str, device_raw: dict[str, Any]) -> None:
        super().__init__(coordinator, device_id, device_raw)
        self._attr_unique_id = f"{device_id}_firmware"
        self._attr_name = "Версия прошивки"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data.get(self._device_id, {})
        return data.get("fwVersion") or data.get("base", {}).get("fwVersion") or "14.00007.01.28"


class AJCloudIpSensor(AJCloudBaseSensor):
    """Local IP Address sensor."""

    _attr_icon = "mdi:ip-network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AJCloudDataCoordinator, device_id: str, device_raw: dict[str, Any]) -> None:
        super().__init__(coordinator, device_id, device_raw)
        self._attr_unique_id = f"{device_id}_ip"
        self._attr_name = "IP-адрес в сети"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data.get(self._device_id, {})
        net = data.get("networkConfig", {})
        return net.get("localIp") or data.get("localIp")

