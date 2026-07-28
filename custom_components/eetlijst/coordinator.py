"""Coordinator for Eetlijst integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from logging import getLogger
from typing import override

import httpx
from eetlijst_py import Eetlijst
from eetlijst_py.generated import timestamptz_comparison_exp
from eetlijst_py.services.events.types import Event, WhereEvent
from eetlijst_py.services.group_list.types import ListItem, WhereListItem
from eetlijst_py.services.groups.types import Group
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

    group: Group
    events: list[Event]
    shopping_items: list[ListItem]


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
        """Set up the coordinator, API client, and real-time subscriptions."""
        self.client = Eetlijst(
            api_key=self.config_entry.data[CONF_API_TOKEN],
            http_client=get_async_client(self.hass),
        )

        # Spawn background subscription tasks managed by HA entry lifecycle
        self.config_entry.async_create_background_task(
            self.hass,
            self._listen_group_subscription(),
            "eetlijst_group_subscription",
        )
        self.config_entry.async_create_background_task(
            self.hass,
            self._listen_events_subscription(),
            "eetlijst_events_subscription",
        )
        self.config_entry.async_create_background_task(
            self.hass,
            self._listen_items_subscription(),
            "eetlijst_items_subscription",
        )

    def _get_event_filter_and_limit(
        self,
    ) -> tuple[str, WhereEvent | None, int | None]:
        """Helper to compute filtering parameters from entry config/options."""
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

        where_filter: WhereEvent | None = None
        if previous_days > 0:
            since_date = dt_util.now() - timedelta(days=previous_days)
            where_filter = WhereEvent(
                start_date=timestamptz_comparison_exp(gte=since_date)
            )

        return group_id, where_filter, limit

    async def _listen_group_subscription(self) -> None:
        """Listen to real-time group updates."""
        group_id = self.config_entry.data[CONF_GROUP_ID]
        while True:
            try:
                async for group in self.client.groups.get_subscription(
                    group_id=group_id,
                    include_users=True,
                ):
                    if self.data is not None:
                        self.async_set_updated_data(
                            EetlijstData(
                                group=group,
                                events=self.data.events,
                                shopping_items=self.data.shopping_items,
                            )
                        )
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOGGER.warning(
                    "Group subscription stream interrupted (%s). Reconnecting in 5s...",
                    err,
                )
                await asyncio.sleep(5)

    async def _listen_events_subscription(self) -> None:
        """Listen to real-time event updates."""
        while True:
            try:
                group_id, where_filter, limit = self._get_event_filter_and_limit()
                async for events in self.client.events.all_subscription(
                    group_id,
                    where=where_filter,
                    limit=limit,
                    include_attendees=True,
                ):
                    if self.data is not None:
                        self.async_set_updated_data(
                            EetlijstData(
                                group=self.data.group,
                                events=events,
                                shopping_items=self.data.shopping_items,
                            )
                        )
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOGGER.warning(
                    "Events subscription stream interrupted (%s). Reconnecting in 5s...",
                    err,
                )
                await asyncio.sleep(5)

    async def _listen_items_subscription(self) -> None:
        """Listen to real-time shopping list updates."""
        group_id = self.config_entry.data[CONF_GROUP_ID]
        where_filter = WhereListItem(active={"_eq": True})
        while True:
            try:
                async for items in self.client.groups.list.items_subscription(
                    group_id=group_id,
                    where=where_filter,
                ):
                    if self.data is not None:
                        self.async_set_updated_data(
                            EetlijstData(
                                group=self.data.group,
                                events=self.data.events,
                                shopping_items=items,
                            )
                        )
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOGGER.warning(
                    "Shopping items subscription stream interrupted (%s). Reconnecting in 5s...",
                    err,
                )
                await asyncio.sleep(5)

    @override
    async def _async_update_data(self) -> EetlijstData:
        """Fetch group info, events, and shopping list items via REST/GraphQL polling sync."""
        group_id, where_filter, limit = self._get_event_filter_and_limit()

        _LOGGER.debug(
            "Fetching Eetlijst sync data for group %s (limit=%s)",
            group_id,
            limit,
        )

        try:
            async with asyncio.timeout(15):
                group, events, shopping_items = await asyncio.gather(
                    self.client.groups.get(group_id=group_id, include_users=True),
                    self.client.events.all(
                        group_id,
                        where=where_filter,
                        limit=limit,
                        include_attendees=True,
                    ),
                    self.client.groups.list.items(
                        group_id=group_id,
                        where=WhereListItem(active={"_eq": True}),
                    ),
                )

            return EetlijstData(
                group=group,
                events=events,
                shopping_items=shopping_items,
            )

        except TimeoutError as err:
            raise UpdateFailed(
                f"Timeout fetching Eetlijst data for group {group_id}"
            ) from err

        except httpx.HTTPStatusError as err:
            if err.response.status_code in (401, 403):
                raise ConfigEntryAuthFailed(
                    "Invalid API token or unauthorized"
                ) from err

            status = err.response.status_code
            body = err.response.text[:200] if err.response else ""
            raise UpdateFailed(
                f"HTTP {status} fetching Eetlijst data: {body or str(err) or repr(err)}"
            ) from err

        except httpx.RequestError as err:
            raise UpdateFailed(
                f"Error communicating with API ({type(err).__name__}): {str(err) or repr(err)}"
            ) from err

        except Exception as err:
            raise UpdateFailed(
                f"Unexpected error ({type(err).__name__}): {str(err) or repr(err)}"
            ) from err
