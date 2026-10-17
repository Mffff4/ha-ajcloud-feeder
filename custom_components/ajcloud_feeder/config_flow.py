"""Config flow for AJCloud Smart Pet Feeder."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AJCloudApiClient, AJCloudAuthError, AJCloudApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate user credentials against AJCloud."""
    session = async_get_clientsession(hass)
    client = AJCloudApiClient(session)

    await client.async_login(data[CONF_USERNAME], data[CONF_PASSWORD])
    devices = await client.async_fetch_devices()

    if not devices:
        raise AJCloudApiError("No AJCloud devices found on this account")

    return {
        "title": f"AJCloud ({data[CONF_USERNAME]})",
        "devices": devices,
        "uid": client.uid,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AJCloud Smart Pet Feeder."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except AJCloudAuthError:
                errors["base"] = "invalid_auth"
            except AJCloudApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception in config flow")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info.get("uid") or user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
