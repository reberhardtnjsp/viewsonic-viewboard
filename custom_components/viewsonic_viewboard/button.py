"""Buttons: the board's keypad keys."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
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
    async_add_entities(ViewBoardKeyButton(entry.runtime_data, key) for key in KEYPAD_KEYS)


class ViewBoardKeyButton(ViewBoardEntity, ButtonEntity):
    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator, f"key_{key}")
        self._value = KEYPAD_KEYS[key]
        self._attr_name, self._attr_icon = KEY_INFO[key]

    async def async_press(self) -> None:
        await self.coordinator.async_set("A", self._value)
