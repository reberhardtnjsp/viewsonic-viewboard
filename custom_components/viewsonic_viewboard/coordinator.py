"""Polling coordinator for a ViewBoard."""

from __future__ import annotations

import logging
import socket
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import ViewBoardClient, ViewBoardConnectionError
from .const import CONF_ARP_MAC, CONF_MAC, DOMAIN, SCAN_INTERVAL, SEARCH_COOLDOWN
from .discovery import async_find_board, read_arp_table

_LOGGER = logging.getLogger(__name__)

type ViewBoardConfigEntry = ConfigEntry[ViewBoardCoordinator]


def _send_magic_packets(macs: list[str], ip: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for mac in macs:
            packet = b"\xff" * 6 + bytes.fromhex(mac.replace(":", "")) * 16
            for target in ("255.255.255.255", ip):
                try:
                    sock.sendto(packet, (target, 9))
                except OSError as err:
                    _LOGGER.debug("Wake-on-LAN to %s via %s failed: %s", mac, target, err)


class ViewBoardCoordinator(DataUpdateCoordinator[dict]):
    """Polls the board. When it can't be reached, data["online"] is False
    (rather than failing) so the power entity can still offer turn-on.

    The board is identified by MAC; the IP is only its last-known address. If it stops
    answering there, or a different board answers, the local network is searched for it."""

    config_entry: ViewBoardConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ViewBoardConfigEntry, client: ViewBoardClient) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {entry.title}", update_interval=SCAN_INTERVAL
        )
        self.client = client
        self._last_search = -SEARCH_COOLDOWN

    @property
    def macs(self) -> set[str]:
        """Every MAC known for this board: the one it reports and the one seen on the wire."""
        return {m for m in (self.config_entry.data.get(CONF_MAC), self.config_entry.data.get(CONF_ARP_MAC)) if m}

    async def _async_update_data(self) -> dict:
        status = await self._async_poll()
        if status is None and await self.async_relocate():
            status = await self._async_poll()
        if status is None:
            return {"online": False}
        status["online"] = True
        await self._learn_arp_mac()
        return status

    async def _async_poll(self) -> dict | None:
        """Status of the board at its current IP, or None if it isn't there."""
        try:
            status = await self.client.get_status()
        except ViewBoardConnectionError as err:
            _LOGGER.debug("ViewBoard %s offline: %s", self.client.host, err)
            return None
        if status.get("mac") and self.config_entry.data.get(CONF_MAC) and status["mac"] not in self.macs:
            _LOGGER.info(
                "A different ViewBoard (%s) now answers at %s; looking for %s",
                status["mac"], self.client.host, self.config_entry.title,
            )
            return None
        return status

    async def async_relocate(self, force: bool = False) -> bool:
        """Search the local network for this board's MAC. Returns True if it was found at a new IP."""
        if not force and time.monotonic() - self._last_search < SEARCH_COOLDOWN:
            return False
        self._last_search = time.monotonic()
        if not (macs := self.macs):
            return False
        new_ip = await async_find_board(self.hass, macs)
        if not new_ip or new_ip == self.client.host:
            return False
        _LOGGER.warning(
            "ViewBoard %s moved from %s to %s; updating its address", self.config_entry.title, self.client.host, new_ip
        )
        self.client.host = new_ip
        self.hass.config_entries.async_update_entry(self.config_entry, data={**self.config_entry.data, CONF_HOST: new_ip})
        device_registry = dr.async_get(self.hass)
        if device := device_registry.async_get_device(identifiers={(DOMAIN, self.config_entry.unique_id)}):
            device_registry.async_update_device(device.id, configuration_url=f"http://{new_ip}")
        return True

    async def _learn_arp_mac(self) -> None:
        """The MAC the board reports can differ from the one on the wire; remember both
        (for Wake-on-LAN, and so the board can be found by ARP after its IP changes)."""
        entry = self.config_entry
        mac = (await self.hass.async_add_executor_job(read_arp_table)).get(self.client.host)
        if mac and mac != entry.data.get(CONF_ARP_MAC):
            self.hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_ARP_MAC: mac})

    async def async_set(self, cmd: str, value: str) -> None:
        """Send a set command, raising a user-facing error if it fails, then refresh."""
        try:
            ok = await self.client.set(cmd, value)
        except ViewBoardConnectionError as err:
            raise HomeAssistantError(f"ViewBoard {self.client.host} is not reachable") from err
        if not ok:
            raise HomeAssistantError(
                "The ViewBoard rejected that command (it may not apply to the current input)"
            )
        await self.async_request_refresh()

    async def async_turn_on(self) -> None:
        if macs := sorted(self.macs):
            await self.hass.async_add_executor_job(_send_magic_packets, macs, self.client.host)
        try:
            await self.client.set("!", "001")
        except ViewBoardConnectionError:
            pass  # asleep with networking off; Wake-on-LAN is all we can do
        await self.async_request_refresh()
