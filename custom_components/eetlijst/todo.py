"""Todo platform for Eetlijst shopping list integration."""

from eetlijst_py.generated import eetschema_list_insert_input
from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import EetlijstConfigEntry, EetlijstCoordinator


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EetlijstConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Eetlijst todo list entity."""
    coordinator = entry.runtime_data
    async_add_entities([EetlijstTodoListEntity(coordinator, entry.data["group_id"])])


class EetlijstTodoListEntity(CoordinatorEntity[EetlijstCoordinator], TodoListEntity):
    """Representation of an Eetlijst Shopping List entity."""

    _attr_has_entity_name = True
    _attr_name = "Shopping List"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: EetlijstCoordinator, group_id: str) -> None:
        """Initialize the todo list entity."""
        super().__init__(coordinator)
        self._group_id = group_id
        self._attr_unique_id = f"eetlijst_{group_id}_shopping_list"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Return all active shopping list items."""
        if not self.coordinator.data or self.coordinator.data.shopping_items is None:
            return None

        items = []
        for item in self.coordinator.data.shopping_items:
            status = (
                TodoItemStatus.COMPLETED
                if item.checked
                else TodoItemStatus.NEEDS_ACTION
            )
            items.append(
                TodoItem(
                    uid=str(item.id),
                    summary=item.text,
                    status=status,
                )
            )
        return items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add item to Eetlijst list."""
        if not item.summary:
            return
        payload = eetschema_list_insert_input(
            text=item.summary,
            group_id=self._group_id,
            active=True,
        )
        await self.coordinator.client.groups.list.create_item(payload)
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Check or uncheck an item on the Eetlijst list."""
        if not item.uid:
            return
        checked = item.status == TodoItemStatus.COMPLETED
        await self.coordinator.client.groups.list.check_item(
            item_id=item.uid,
            check=checked,
        )
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Remove an item from Eetlijst list."""
        for uid in uids:
            await self.coordinator.client.groups.list.remove_item(item_id=uid)
        await self.coordinator.async_request_refresh()
