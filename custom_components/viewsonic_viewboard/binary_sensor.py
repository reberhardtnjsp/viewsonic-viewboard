"""Binary sensors: input signal detected, board online."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ViewBoardConfigEntry
from .entity import ViewBoardEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ViewBoardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([ViewBoardSignalSensor(coordinator, "signal"), ViewBoardOnlineSensor(coordinator, "online")])


class ViewBoardSignalSensor(ViewBoardEntity, BinarySensorEntity):
    _attr_name = "Input signal"
    _attr_icon = "mdi:video-input-component"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("signal")


class ViewBoardOnlineSensor(ViewBoardEntity, BinarySensorEntity):
    _attr_name = "Network control"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("online", False)
