"""Select: input source."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import INPUT_SOURCES, SOURCE_CODES
from .coordinator import ViewBoardConfigEntry
from .entity import ViewBoardEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ViewBoardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([ViewBoardInputSelect(entry.runtime_data, "input")])


class ViewBoardInputSelect(ViewBoardEntity, SelectEntity):
    _attr_name = "Input"
    _attr_icon = "mdi:video-input-hdmi"
    _attr_options = list(SOURCE_CODES)

    @property
    def current_option(self) -> str | None:
        return INPUT_SOURCES.get(self.coordinator.data.get("input"))

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set('"', SOURCE_CODES[option])
