"""Config flow for Eetlijst integration."""

import asyncio
import logging
from collections.abc import Mapping
from typing import Any, override

import httpx
import voluptuous as vol
from eetlijst_py import Eetlijst
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    CONF_GROUP_ID,
    CONF_LIMIT,
    CONF_PREVIOUS_DAYS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_LIMIT,
    DEFAULT_PREVIOUS_DAYS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
        vol.Required(CONF_GROUP_ID): str,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
        vol.Optional(CONF_PREVIOUS_DAYS, default=DEFAULT_PREVIOUS_DAYS): int,
        vol.Optional(CONF_LIMIT, default=DEFAULT_LIMIT): int,
    }
)


async def _validate_input(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> None:
    """Validate user input allows us to connect and group exists."""
    client = Eetlijst(
        api_key=data[CONF_API_TOKEN],
        http_client=get_async_client(hass),
    )

    async with asyncio.timeout(10):
        await client.me.get()
        await client.groups.get(group_id=data[CONF_GROUP_ID], include_users=False)


class EetlijstConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eetlijst."""

    VERSION = 1

    async def async_step_reauth(
        self, _entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with Eetlijst."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with Eetlijst."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            test_data = {**reauth_entry.data, **user_input}

            errors = await self._async_validate_or_error(test_data)

            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                    },
                )

        reauth_schema = vol.Schema({vol.Required(CONF_API_TOKEN): str})

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=reauth_schema,
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_GROUP_ID])
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_or_error(user_input)

            if not errors:
                return self.async_create_entry(
                    title=f"Eetlijst ({user_input[CONF_GROUP_ID]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def _async_validate_or_error(self, config: dict[str, Any]) -> dict[str, str]:
        """Validate configuration and return any error keys."""
        errors: dict[str, str] = {}

        try:
            await _validate_input(self.hass, config)
        except httpx.HTTPStatusError as err:
            if err.response.status_code in (401, 403):
                errors["base"] = "invalid_auth"
            elif err.response.status_code == 404:
                errors["base"] = "group_not_found"
            else:
                errors["base"] = "cannot_connect"
        except httpx.RequestError, TimeoutError:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception validating Eetlijst connection")
            errors["base"] = "unknown"

        return errors
