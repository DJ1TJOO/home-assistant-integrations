from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.eetlijst.coordinator import EetlijstCoordinator

from .const import DOMAIN


class EetlijstBaseEntity(CoordinatorEntity[EetlijstCoordinator]):
    """Base entity for all Eetlijst entities to share device info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EetlijstCoordinator, group_id: str) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._group_id = group_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information linking entities to the group."""
        group_name = (
            self.coordinator.data.group.name
            if self.coordinator.data and self.coordinator.data.group
            else f"Group {self._group_id}"
        )

        return DeviceInfo(
            identifiers={(DOMAIN, self._group_id)},
            name=f"Eetlijst {group_name}",
            manufacturer="Eetlijst",
            model="Group Management",
        )
