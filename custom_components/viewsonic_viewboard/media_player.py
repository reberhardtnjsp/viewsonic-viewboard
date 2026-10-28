"""Media player: power, volume, mute and input in one card."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import INPUT_SOURCES, SOURCE_CODES
from .coordinator import ViewBoardConfigEntry
from .entity import ViewBoardEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ViewBoardConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([ViewBoardMediaPlayer(entry.runtime_data, "media_player")])


class ViewBoardMediaPlayer(ViewBoardEntity, MediaPlayerEntity):
    _attr_name = None  # use the device name
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_source_list = list(SOURCE_CODES)
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    @property
    def available(self) -> bool:
        # Stay available while the board is unreachable so it can be woken up.
        return self.coordinator.last_update_success

    @property
    def _data(self) -> dict:
        return self.coordinator.data

    @property
    def state(self) -> MediaPlayerState:
        return MediaPlayerState.ON if self._data.get("power") else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        vol = self._data.get("volume")
        return vol / 100 if vol is not None else None

    @property
    def is_volume_muted(self) -> bool | None:
        return self._data.get("mute")

    @property
    def source(self) -> str | None:
        code = self._data.get("input")
        return INPUT_SOURCES.get(code, f"Unknown ({code})") if code else None

    async def async_turn_on(self) -> None:
        await self.coordinator.async_turn_on()

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set("!", "000")

    async def async_set_volume_level(self, volume: float) -> None:
        await self.coordinator.async_set("5", f"{round(volume * 100):03d}")

    async def async_volume_up(self) -> None:
        await self.coordinator.async_set("5", "901")

    async def async_volume_down(self) -> None:
        await self.coordinator.async_set("5", "900")

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.async_set("6", "001" if mute else "000")

    async def async_select_source(self, source: str) -> None:
        await self.coordinator.async_set('"', SOURCE_CODES[source])
