"""Switches: mute, screen on/off and the panel locks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ViewBoardConfigEntry
from .entity import ViewBoardEntity


@dataclass(frozen=True, kw_only=True)
class ViewBoardSwitchDescription(SwitchEntityDescription):
    command: str
    state_key: str | None  # None = the board can't report it, so the state is assumed


SWITCHES = (
    ViewBoardSwitchDescription(key="power", name="Power", icon="mdi:power", command="!", state_key="power"),
    ViewBoardSwitchDescription(key="mute", name="Mute", icon="mdi:volume-off", command="6", state_key="mute"),
    ViewBoardSwitchDescription(
        key="screen", name="Screen", icon="mdi:monitor", command="(", state_key="backlight"
    ),
    ViewBoardSwitchDescription(
        key="button_lock", name="Button lock", icon="mdi:lock", command="8", state_key="button_lock",
        entity_category=EntityCategory.CONFIG,
    ),
    ViewBoardSwitchDescription(
        key="power_lock", name="Power button lock", icon="mdi:power-plug-off", command="4",
        state_key="power_lock", entity_category=EntityCategory.CONFIG,
    ),
    ViewBoardSwitchDescription(
        key="menu_lock", name="Menu lock", icon="mdi:menu", command=">", state_key=None,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ViewBoardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(ViewBoardSwitch(entry.runtime_data, desc) for desc in SWITCHES)


class ViewBoardSwitch(ViewBoardEntity, SwitchEntity):
    entity_description: ViewBoardSwitchDescription

    def __init__(self, coordinator, description: ViewBoardSwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_assumed_state = description.state_key is None
        self._assumed: bool | None = None

    @property
    def available(self) -> bool:
        if self.entity_description.key == "power":
            return self.coordinator.last_update_success  # allow turning on from standby
        return super().available

    @property
    def is_on(self) -> bool | None:
        if key := self.entity_description.state_key:
            return self.coordinator.data.get(key)
        return self._assumed

    async def _set(self, on: bool) -> None:
        if self.entity_description.key == "power" and on:
            await self.coordinator.async_turn_on()
            return
        await self.coordinator.async_set(self.entity_description.command, "001" if on else "000")
        if self._attr_assumed_state:
            self._assumed = on
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
