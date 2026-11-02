"""Async client for the ViewSonic ViewBoard LAN control protocol (TCP port 5000).

Packets are ASCII:  <len><id:2><type><cmd><value:3><CR>
  set:   "801s!001\r"  -> "401+\r" (accepted) or "401-\r" (rejected)
  get:   "801gl000\r"  -> "801rl001\r"
  info:  "801g7000\r"  -> "201r7<serial padded to 32 bytes>\r"
The board also pushes unsolicited "801r..." lines when settings change locally,
so replies are matched by command rather than assumed to be the next line.
"""

from __future__ import annotations

import asyncio
import logging

from .const import DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 3.0

# name -> get command char
STATUS_COMMANDS = {
    "power": "l",
    "input": "j",
    "volume": "f",
    "mute": "g",
    "brightness": "b",
    "contrast": "a",
    "backlight": "h",
    "button_lock": "p",
    "power_lock": "o",
    "temperature": "0",
    "operating_hours": "1",
    "mac": "5",  # lets the coordinator notice when a different board has taken this IP
}
INFO_COMMANDS = {"model": "4", "mac": "5", "serial": "7", "firmware": "8"}


def norm_mac(mac: str | None) -> str | None:
    """'20-9B-E6-2E-A9-92', '2:15:...' or '209be62ea992' -> '20:9b:e6:2e:a9:92'. None if invalid,
    blank, broadcast or multicast."""
    if not mac:
        return None
    mac = mac.strip().lower()
    if len(mac) == 12 and all(c in "0123456789abcdef" for c in mac):
        parts = [mac[i : i + 2] for i in range(0, 12, 2)]
    else:
        parts = mac.replace("-", ":").split(":")
    try:
        if len(parts) != 6 or any(not 1 <= len(p) <= 2 for p in parts):
            return None
        octets = [int(p, 16) for p in parts]
    except ValueError:
        return None
    if octets[0] & 1 or not any(octets):
        return None
    return ":".join(f"{o:02x}" for o in octets)


class ViewBoardError(Exception):
    """Base error."""


class ViewBoardConnectionError(ViewBoardError):
    """The board could not be reached."""


class ViewBoardClient:
    """Talks to one ViewBoard."""

    def __init__(self, host: str, port: int = DEFAULT_PORT, display_id: str = "01") -> None:
        self.host = host
        self.port = port
        self._id = display_id
        self._lock = asyncio.Lock()

    async def _open(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        try:
            return await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), TIMEOUT
            )
        except (OSError, TimeoutError) as err:
            raise ViewBoardConnectionError(f"Cannot connect to {self.host}: {err}") from err

    @staticmethod
    async def _close(writer: asyncio.StreamWriter) -> None:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass

    async def _exchange(self, reader, writer, packet: str, expect: str) -> str | None:
        """Send a packet, return the payload after `expect`, or None if rejected/no reply."""
        writer.write(packet.encode("ascii"))
        await writer.drain()
        rejected = f"{self._id}-"
        loop = asyncio.get_running_loop()
        deadline = loop.time() + TIMEOUT
        while (remaining := deadline - loop.time()) > 0:
            try:
                line = await asyncio.wait_for(reader.readuntil(b"\r"), remaining)
            except (TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
                return None
            # drop the length byte and trailing CR / padding
            text = line.decode("ascii", "replace")[1:].rstrip("\r").rstrip(" \x00")
            if text.startswith(expect):
                return text[len(expect):]
            if text == rejected:
                return None
            _LOGGER.debug("%s: ignoring unsolicited %r", self.host, text)
        return None

    async def query(self, commands: dict[str, str]) -> dict[str, str | None]:
        """Run several get commands over one connection. Returns name -> raw value."""
        async with self._lock:
            reader, writer = await self._open()
            try:
                result = {}
                for name, cmd in commands.items():
                    result[name] = await self._exchange(
                        reader, writer, f"8{self._id}g{cmd}000\r", f"{self._id}r{cmd}"
                    )
                return result
            except OSError as err:
                raise ViewBoardConnectionError(str(err)) from err
            finally:
                await self._close(writer)

    async def set(self, cmd: str, value: str) -> bool:
        """Run one set command. Returns True if the board accepted it."""
        async with self._lock:
            reader, writer = await self._open()
            try:
                reply = await self._exchange(
                    reader, writer, f"8{self._id}s{cmd}{value}\r", f"{self._id}+"
                )
                return reply == ""
            except OSError as err:
                raise ViewBoardConnectionError(str(err)) from err
            finally:
                await self._close(writer)

    async def get_device_info(self) -> dict[str, str | None]:
        """Model, MAC, serial and firmware, plus power to confirm it speaks the protocol."""
        info = await self.query({"power": "l", **INFO_COMMANDS})
        info["mac"] = norm_mac(info.get("mac"))
        return info

    async def get_reported_mac(self) -> str | None:
        """The MAC the board reports; None if whatever is at this address isn't a ViewBoard."""
        return norm_mac((await self.query({"mac": "5"}))["mac"])

    async def get_status(self) -> dict:
        """Current state, parsed into Python types."""
        raw = await self.query(STATUS_COMMANDS)
        status: dict = {"mac": norm_mac(raw["mac"])}
        for key in ("power", "mute", "backlight", "button_lock", "power_lock"):
            status[key] = raw[key] == "001" if raw[key] is not None else None
        for key in ("volume", "brightness", "contrast", "temperature", "operating_hours"):
            try:
                status[key] = int(raw[key]) if raw[key] is not None else None
            except ValueError:
                status[key] = None
        if (src := raw["input"]) and len(src) == 3:
            # first digit = signal detected, last two = source code
            status["signal"] = src[0] == "1"
            status["input"] = "0" + src[1:]
        else:
            status["signal"] = status["input"] = None
        return status
