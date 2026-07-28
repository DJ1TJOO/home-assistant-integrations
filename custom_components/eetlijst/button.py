"""Button platform for Eetlijst integration."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import EetlijstConfigEntry
from .device import EetlijstBaseEntity


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EetlijstConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Eetlijst button platform."""
    coordinator = entry.runtime_data
    group_id = entry.data["group_id"]

    async_add_entities([EetlijstSyncButton(coordinator, group_id)])


class EetlijstSyncButton(EetlijstBaseEntity, ButtonEntity):
    """Representation of an Eetlijst sync button."""

    _attr_icon = "mdi:sync"
    _attr_name = "Sync Data"

    def __init__(self, coordinator, group_id: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, group_id)
        self._attr_unique_id = f"eetlijst_{group_id}_sync_button"

    async def async_press(self) -> None:
        """Handle the button press."""
        # Trigger an immediate coordinator data refresh
        await self.coordinator.async_request_refresh()
