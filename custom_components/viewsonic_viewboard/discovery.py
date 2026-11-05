"""Find a ViewBoard on the local network by MAC address after its IP has changed.

1. Look in the ARP cache.
2. Otherwise sweep the subnet(s) Home Assistant is on, plus the /24 around every added board's
   last-known address and any networks set in a board's options (for boards behind a router).
   An empty UDP packet to every local address makes the OS ARP-resolve them all, then every host
   with port 5000 open is asked for the MAC it reports, which also works across a router.
The sweep is shared by all boards and cached briefly, so several boards moving at once
(e.g. after a network outage) cost one scan.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
import subprocess
import time

from homeassistant.components import network
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .api import ViewBoardClient, ViewBoardError, norm_mac
from .const import CONF_SEARCH_NETWORKS, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

MAX_SCAN_HOSTS = 4096  # never sweep more than a /20 per network
MAX_TOTAL_HOSTS = 16384
SCAN_CACHE_SECONDS = 60

_IP_RE = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
_MAC_RE = re.compile(r"(?<![0-9a-fA-F:-])([0-9a-fA-F]{1,2}(?:[:-][0-9a-fA-F]{1,2}){5})(?![0-9a-fA-F:-])")


def read_arp_table() -> dict[str, str]:
    """The ARP cache as {ip: mac}. /proc on Linux (Home Assistant OS), `arp` elsewhere."""
    table: dict[str, str] = {}
    try:
        with open("/proc/net/arp", encoding="ascii") as arp:
            next(arp, None)
            for line in arp:
                parts = line.split()
                if len(parts) > 3 and parts[2] != "0x0" and (mac := norm_mac(parts[3])):
                    table[parts[0]] = mac
        return table
    except OSError:
        pass
    try:
        out = subprocess.run(["arp", "-an"], capture_output=True, text=True, timeout=5, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return table
    for line in out.splitlines():
        ip_m, mac_m = _IP_RE.search(line), _MAC_RE.search(line)
        if ip_m and mac_m and (mac := norm_mac(mac_m.group(1))):
            table[ip_m.group(1)] = mac
    return table


def parse_network(text: str) -> ipaddress.IPv4Network:
    """A private IPv4 network of at most MAX_SCAN_HOSTS addresses, e.g. "10.3.12.0/22".
    Raises ValueError otherwise."""
    net = ipaddress.ip_network(text.strip(), strict=False)
    if not isinstance(net, ipaddress.IPv4Network) or not net.is_private or net.is_loopback:
        raise ValueError("not a private IPv4 network")
    if net.num_addresses > MAX_SCAN_HOSTS:
        raise ValueError("network too large")
    return net


async def _local_networks(hass: HomeAssistant) -> dict[ipaddress.IPv4Network, str]:
    """{network: this host's address on it} for the private IPv4 subnets of the enabled adapters."""
    nets = {}
    for adapter in await network.async_get_adapters(hass):
        if not adapter["enabled"]:
            continue
        for addr in adapter["ipv4"]:
            net = ipaddress.ip_network(f"{addr['address']}/{addr['network_prefix']}", strict=False)
            if not net.is_private or net.is_loopback or net.prefixlen >= 31:
                continue
            if net.num_addresses > MAX_SCAN_HOSTS:
                net = ipaddress.ip_network(f"{addr['address']}/{33 - MAX_SCAN_HOSTS.bit_length()}", strict=False)
            nets[net] = addr["address"]
    return nets


def _remote_networks(hass: HomeAssistant) -> list[ipaddress.IPv4Network]:
    """Networks to search beyond the local ones: those set in any board's options, and the /24
    around every board's last-known address (boards behind a router usually stay nearby)."""
    nets = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        for text in entry.options.get(CONF_SEARCH_NETWORKS, []):
            try:
                nets.append(parse_network(text))
            except ValueError:
                _LOGGER.warning("Ignoring invalid network to search: %s", text)
        try:
            nets.append(parse_network(f"{entry.data[CONF_HOST]}/24"))
        except (KeyError, ValueError):
            pass
    return nets


async def _search_hosts(hass: HomeAssistant) -> tuple[list[str], list[str]]:
    """(addresses to search, the subset on Home Assistant's own subnets)."""
    local = await _local_networks(hass)
    own = set(local.values())
    hosts: list[str] = []
    for net in local:
        hosts.extend(str(h) for h in net.hosts() if str(h) not in own)
    local_hosts = list(dict.fromkeys(hosts))
    for net in _remote_networks(hass):
        if not any(net.subnet_of(n) for n in local):
            hosts.extend(str(h) for h in net.hosts())
    hosts = list(dict.fromkeys(hosts))
    if len(hosts) > MAX_TOTAL_HOSTS:
        _LOGGER.warning("Only searching the first %d of %d addresses", MAX_TOTAL_HOSTS, len(hosts))
        hosts = hosts[:MAX_TOTAL_HOSTS]
    return hosts, local_hosts


def _poke_all(hosts: list[str]) -> None:
    """One empty UDP packet per address, so the OS ARP-resolves each (no special permissions needed)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for i, host in enumerate(hosts):
            try:
                sock.sendto(b"", (host, 9))
            except OSError:
                pass
            if i % 64 == 63:
                time.sleep(0.02)  # don't flood the network


async def _port_open(host: str, sem: asyncio.Semaphore) -> bool:
    async with sem:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, DEFAULT_PORT), 0.7)
        except (OSError, TimeoutError):
            return False
        writer.close()
        return True


async def _reported_mac(host: str, sem: asyncio.Semaphore) -> str | None:
    async with sem:
        try:
            return await ViewBoardClient(host).get_reported_mac()
        except ViewBoardError:
            return None


async def _async_sweep(hass: HomeAssistant) -> dict[str, set[str]]:
    """{ip: MACs seen for it} for every ViewBoard found on the searched networks."""
    hosts, local_hosts = await _search_hosts(hass)
    if not hosts:
        _LOGGER.warning("Couldn't determine a network to search for ViewBoards")
        return {}
    _LOGGER.debug("Searching %d addresses for ViewBoards", len(hosts))
    await hass.async_add_executor_job(_poke_all, local_hosts)  # ARP only resolves local addresses
    port_sem = asyncio.Semaphore(128)
    open_flags = await asyncio.gather(*(_port_open(h, port_sem) for h in hosts))
    open_hosts = [h for h, ok in zip(hosts, open_flags, strict=True) if ok]
    await asyncio.sleep(1)  # let the remaining ARP replies land
    arp = await hass.async_add_executor_job(read_arp_table)
    query_sem = asyncio.Semaphore(32)
    reported = await asyncio.gather(*(_reported_mac(h, query_sem) for h in open_hosts))
    found = {}
    for host, mac in zip(open_hosts, reported, strict=True):
        if mac:  # answers the ViewBoard protocol (Macs use port 5000 for AirPlay too)
            found[host] = {mac} | ({arp[host]} if host in arp else set())
    _LOGGER.debug("Found %d ViewBoards", len(found))
    return found


async def async_find_board(hass: HomeAssistant, macs: set[str]) -> str | None:
    """Current IP of the board with any of these MACs, or None."""
    # 1. ARP cache: cheap, and enough when the board's new IP was recently in use
    arp = await hass.async_add_executor_job(read_arp_table)
    for host, mac in arp.items():
        if mac in macs:
            try:
                if await ViewBoardClient(host).get_reported_mac():
                    return host
            except ViewBoardError:
                pass

    # 2. Shared sweep of the local subnet(s) and the boards' own networks
    data = hass.data.setdefault(DOMAIN, {})
    lock = data.setdefault("scan_lock", asyncio.Lock())
    async with lock:
        cached = data.get("scan")
        if cached and time.monotonic() - cached[0] < SCAN_CACHE_SECONDS:
            found = cached[1]
        else:
            found = await _async_sweep(hass)
            data["scan"] = (time.monotonic(), found)
    return next((host for host, seen in found.items() if seen & macs), None)
