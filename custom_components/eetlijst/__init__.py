"""The Eetlijst integration."""

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import EetlijstConfigEntry, EetlijstCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: EetlijstConfigEntry) -> bool:
    """Set up Eetlijst from a config entry."""
    coordinator = EetlijstCoordinator(hass, entry)

    # Perform initial setup (_async_setup) and initial API data fetch
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EetlijstConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
