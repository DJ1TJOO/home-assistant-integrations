"""Coordinator for Eetlijst integration."""

from dataclasses import dataclass
from datetime import timedelta
from logging import getLogger
from typing import override

import httpx
from eetlijst_py import Eetlijst
from eetlijst_py.generated import (
    ItemFields,
    eetschema_event_bool_exp,
    eetschema_list_bool_exp,
    timestamptz_comparison_exp,
)
from eetlijst_py.services.events.transformers import Event
from eetlijst_py.services.groups.transformers import GroupResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_GROUP_ID,
    CONF_LIMIT,
    CONF_PREVIOUS_DAYS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_LIMIT,
    DEFAULT_PREVIOUS_DAYS,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = getLogger(__name__)

type EetlijstConfigEntry = ConfigEntry[EetlijstCoordinator]


@dataclass
class EetlijstData:
    """Dataclass storing all fetched data for an Eetlijst group."""

    group: GroupResult
    events: list[Event]
    shopping_items: list[ItemFields]


class EetlijstCoordinator(DataUpdateCoordinator[EetlijstData]):
    """Coordinates Eetlijst event, group, and todo updates."""

    config_entry: EetlijstConfigEntry
    client: Eetlijst

    def __init__(self, hass: HomeAssistant, config_entry: EetlijstConfigEntry) -> None:
        """Initialize the coordinator."""
        update_interval_minutes: int = config_entry.options.get(
            CONF_UPDATE_INTERVAL,
            config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=timedelta(minutes=update_interval_minutes),
        )

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator and API client."""
        self.client = Eetlijst(
            api_key=self.config_entry.data[CONF_API_TOKEN],
            http_client=get_async_client(self.hass),
        )

    @override
    async def _async_update_data(self) -> EetlijstData:
        """Fetch group info, events, and shopping list items."""
        group_id: str = self.config_entry.data[CONF_GROUP_ID]

        previous_days: int = self.config_entry.options.get(
            CONF_PREVIOUS_DAYS,
            self.config_entry.data.get(CONF_PREVIOUS_DAYS, DEFAULT_PREVIOUS_DAYS),
        )
        limit: int | None = self.config_entry.options.get(
            CONF_LIMIT,
            self.config_entry.data.get(CONF_LIMIT, DEFAULT_LIMIT),
        )

        if limit is not None and limit <= 0:
            limit = None

        where_filter: eetschema_event_bool_exp | None = None
        if previous_days > 0:
            since_date = dt_util.now() - timedelta(days=previous_days)
            where_filter = eetschema_event_bool_exp(
                start_date=timestamptz_comparison_exp(gte=since_date)
            )

        _LOGGER.debug(
            "Fetching Eetlijst data for group %s (previous_days=%s, limit=%s)",
            group_id,
            previous_days,
            limit,
        )

        try:
            group = await self.client.groups.get(group_id=group_id, include_users=True)
            events = await self.client.events.all(
                group_id,
                where=where_filter,
                limit=limit,
                include_attendees=True,
            )
            shopping_items = await self.client.groups.list.items(
                group_id=group_id,
                where=eetschema_list_bool_exp(active={"_eq": True}),
            )

            return EetlijstData(
                group=group,
                events=events,
                shopping_items=shopping_items,
            )

        except httpx.HTTPStatusError as err:
            if err.response.status_code in (401, 403):
                raise ConfigEntryAuthFailed(
                    "Invalid API token or unauthorized"
                ) from err
            raise UpdateFailed(f"HTTP error fetching Eetlijst data: {err}") from err

        except (httpx.RequestError, TimeoutError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        except Exception as err:
            _LOGGER.exception("Unexpected error fetching Eetlijst data")
            raise UpdateFailed(f"Unexpected error: {err}") from err
