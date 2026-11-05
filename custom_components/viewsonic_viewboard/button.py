"""Buttons: the board's keypad keys."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import KEYPAD_KEYS
from .coordinator import ViewBoardConfigEntry
from .entity import ViewBoardEntity

KEY_INFO = {
    "up": ("Key up", "mdi:arrow-up-bold"),
    "down": ("Key down", "mdi:arrow-down-bold"),
    "left": ("Key left", "mdi:arrow-left-bold"),
    "right": ("Key right", "mdi:arrow-right-bold"),
    "enter": ("Key OK", "mdi:keyboard-return"),
    "input": ("Key input", "mdi:import"),
    "menu": ("Key menu", "mdi:menu"),
    "exit": ("Key exit", "mdi:exit-to-app"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ViewBoardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [*(ViewBoardKeyButton(coordinator, key) for key in KEYPAD_KEYS), ViewBoardSearchButton(coordinator, "search")]
    )


class ViewBoardKeyButton(ViewBoardEntity, ButtonEntity):
    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator, f"key_{key}")
        self._value = KEYPAD_KEYS[key]
        self._attr_name, self._attr_icon = KEY_INFO[key]

    async def async_press(self) -> None:
        await self.coordinator.async_set("A", self._value)


class ViewBoardSearchButton(ViewBoardEntity, ButtonEntity):
    """Search the network for this board by MAC right now (it also happens automatically)."""

    _attr_name = "Search network for board"
    _attr_icon = "mdi:magnify-scan"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success  # most useful exactly when the board is unreachable

    async def async_press(self) -> None:
        if self.coordinator.data.get("online"):
            return  # already reachable at its current address
        if not await self.coordinator.async_relocate(force=True):
            raise HomeAssistantError(
                f"Couldn't find {self.coordinator.config_entry.title} on the network. "
                "It may be off or unplugged, or on a network not listed in its options."
            )
        await self.coordinator.async_refresh()
