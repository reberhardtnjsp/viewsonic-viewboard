"""Sensors: temperature, operating hours, current input."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import INPUT_SOURCES
from .coordinator import ViewBoardConfigEntry
from .entity import ViewBoardEntity

SENSORS = (
    SensorEntityDescription(
        key="temperature",
        name="Internal temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="operating_hours",
        name="Operating hours",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(key="input", name="Current input", icon="mdi:video-input-hdmi"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ViewBoardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(ViewBoardSensor(entry.runtime_data, desc) for desc in SENSORS)


class ViewBoardSensor(ViewBoardEntity, SensorEntity):
    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, f"sensor_{description.key}")
        self.entity_description = description

    @property
    def native_value(self):
        value = self.coordinator.data.get(self.entity_description.key)
        if self.entity_description.key == "input" and value:
            return INPUT_SOURCES.get(value, f"Unknown ({value})")
        return value
