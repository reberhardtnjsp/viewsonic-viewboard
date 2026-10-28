"""Numbers: volume, brightness, contrast."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ViewBoardConfigEntry
from .entity import ViewBoardEntity


@dataclass(frozen=True, kw_only=True)
class ViewBoardNumberDescription(NumberEntityDescription):
    command: str


NUMBERS = (
    ViewBoardNumberDescription(key="volume", name="Volume", icon="mdi:volume-high", command="5"),
    # Brightness and contrast are only accepted on external inputs (HDMI/DP/PC), not on Android.
    ViewBoardNumberDescription(
        key="brightness", name="Brightness", icon="mdi:brightness-6", command="$",
        entity_category=EntityCategory.CONFIG,
    ),
    ViewBoardNumberDescription(
        key="contrast", name="Contrast", icon="mdi:contrast-box", command="#",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ViewBoardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(ViewBoardNumber(entry.runtime_data, desc) for desc in NUMBERS)


class ViewBoardNumber(ViewBoardEntity, NumberEntity):
    entity_description: ViewBoardNumberDescription
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, description: ViewBoardNumberDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set(self.entity_description.command, f"{round(value):03d}")
