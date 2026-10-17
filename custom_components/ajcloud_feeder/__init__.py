"""The AJCloud Smart Pet Feeder integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AJCloudApiClient, AJCloudApiError, AJCloudAuthError
from .const import (
    ATTR_FEEDER_ID,
    ATTR_PORTIONS,
    DEFAULT_PORTIONS,
    DOMAIN,
    SERVICE_FEED,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.CAMERA,
    Platform.SWITCH,
]


class AJCloudDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to periodically fetch telemetry from AJCloud devices."""

    def __init__(self, hass: HomeAssistant, client: AJCloudApiClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=45),
        )
        self.client = client
        self.last_feed_time: dict[str, datetime | None] = {}
        self.portions_today: dict[str, int] = {}
        self._last_day: int = dt_util.now().day

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest status for all devices."""
        # Reset portions count at midnight
        now = dt_util.now()
        if now.day != self._last_day:
            self.portions_today.clear()
            self._last_day = now.day

        data: dict[str, Any] = {}
        try:
            for device_id in self.client.devices:
                status = await self.client.async_get_device_status(device_id)
                data[device_id] = status
            return data
        except (AJCloudApiError, AJCloudAuthError) as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

    def record_feed(self, device_id: str, portions: int) -> None:
        """Record a successful feeding event."""
        now = dt_util.now()
        self.last_feed_time[device_id] = now
        self.portions_today[device_id] = self.portions_today.get(device_id, 0) + portions
        self.async_update_listeners()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AJCloud from a config entry."""
    session = async_get_clientsession(hass)
    client = AJCloudApiClient(session)

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    await client.async_login(username, password)
    await client.async_fetch_devices()

    coordinator = AJCloudDataCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "portions": {did: DEFAULT_PORTIONS for did in client.devices},
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register feed service
    async def async_handle_feed(call: ServiceCall) -> None:
        """Handle the feed service call."""
        portions = call.data.get(ATTR_PORTIONS, DEFAULT_PORTIONS)
        feeder_id = call.data.get(ATTR_FEEDER_ID)

        if feeder_id:
            await client.async_feed(feeder_id, portions=portions)
            coordinator.record_feed(feeder_id, portions)
        else:
            for did in client.devices:
                await client.async_feed(did, portions=portions)
                coordinator.record_feed(did, portions)

    if not hass.services.has_service(DOMAIN, SERVICE_FEED):
        hass.services.async_register(DOMAIN, SERVICE_FEED, async_handle_feed)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
