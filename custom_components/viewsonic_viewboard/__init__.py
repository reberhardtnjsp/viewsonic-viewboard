"""ViewSonic ViewBoard integration: control ViewBoards over their LAN control port."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .api import ViewBoardClient
from .coordinator import ViewBoardConfigEntry, ViewBoardCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ViewBoardConfigEntry) -> bool:
    coordinator = ViewBoardCoordinator(hass, entry, ViewBoardClient(entry.data[CONF_HOST]))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ViewBoardConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
