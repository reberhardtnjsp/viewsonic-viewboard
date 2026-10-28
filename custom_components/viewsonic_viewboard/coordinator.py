"""Polling coordinator for a ViewBoard."""

from __future__ import annotations

import logging
import socket

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import ViewBoardClient, ViewBoardConnectionError
from .const import CONF_ARP_MAC, CONF_MAC, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type ViewBoardConfigEntry = ConfigEntry[ViewBoardCoordinator]


def _arp_mac(ip: str) -> str | None:
    """Look up an IP in the Linux ARP table (Home Assistant OS / containers)."""
    try:
        with open("/proc/net/arp", encoding="ascii") as arp:
            for line in arp:
                parts = line.split()
                if len(parts) > 3 and parts[0] == ip and parts[3] != "00:00:00:00:00:00":
                    return parts[3].lower()
    except OSError:
        pass
    return None


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
    (rather than failing) so the power entity can still offer turn-on."""

    config_entry: ViewBoardConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ViewBoardConfigEntry, client: ViewBoardClient) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {client.host}", update_interval=SCAN_INTERVAL
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            status = await self.client.get_status()
        except ViewBoardConnectionError as err:
            _LOGGER.debug("ViewBoard %s offline: %s", self.client.host, err)
            return {"online": False}
        status["online"] = True
        await self._learn_arp_mac()
        return status

    async def _learn_arp_mac(self) -> None:
        """The MAC the board reports can differ from the one on the wire; remember both for Wake-on-LAN."""
        entry = self.config_entry
        if entry.data.get(CONF_ARP_MAC):
            return
        if mac := await self.hass.async_add_executor_job(_arp_mac, self.client.host):
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
        macs = {self.config_entry.data.get(CONF_MAC), self.config_entry.data.get(CONF_ARP_MAC)}
        if macs := [m for m in macs if m]:
            await self.hass.async_add_executor_job(_send_magic_packets, macs, self.client.host)
        try:
            await self.client.set("!", "001")
        except ViewBoardConnectionError:
            pass  # asleep with networking off; Wake-on-LAN is all we can do
        await self.async_request_refresh()
