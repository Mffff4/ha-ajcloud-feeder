"""The AJCloud Smart Pet Feeder integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
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

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_FEED_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_FEEDER_ID): cv.string,
        vol.Optional(ATTR_PORTIONS, default=DEFAULT_PORTIONS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=10)
        ),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the AJCloud Smart Pet Feeder component."""
    hass.data.setdefault(DOMAIN, {})

    async def async_handle_feed(call: ServiceCall) -> None:
        """Handle the feed service call."""
        feeder_id: str = call.data[ATTR_FEEDER_ID]
        portions: int = call.data[ATTR_PORTIONS]

        target_client: AJCloudApiClient | None = None
        target_coordinator: AJCloudDataCoordinator | None = None

        for entry_data in hass.data.get(DOMAIN, {}).values():
            if not isinstance(entry_data, dict):
                continue
            client = entry_data.get("client")
            if client and feeder_id in client.devices:
                target_client = client
                target_coordinator = entry_data.get("coordinator")
                break

        if not target_client or not target_coordinator:
            raise ServiceValidationError(
                f"Unknown or disconnected feeder ID: {feeder_id}"
            )

        try:
            await target_client.async_feed(feeder_id, portions=portions)
            target_coordinator.record_feed(feeder_id, portions)
        except Exception as err:
            raise ServiceValidationError(f"Failed to dispense food: {err}") from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_FEED,
        async_handle_feed,
        schema=SERVICE_FEED_SCHEMA,
    )
    return True


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
        except AJCloudAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except (AJCloudApiError, aiohttp.ClientError) as err:
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

    try:
        await client.async_login(username, password)
        await client.async_fetch_devices()
    except AJCloudAuthError as err:
        raise ConfigEntryAuthFailed(f"Invalid credentials for AJCloud: {err}") from err
    except (AJCloudApiError, aiohttp.ClientError) as err:
        raise ConfigEntryNotReady(f"Cannot connect to AJCloud: {err}") from err

    coordinator = AJCloudDataCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "portions": {did: DEFAULT_PORTIONS for did in client.devices},
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
