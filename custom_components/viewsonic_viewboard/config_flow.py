"""Config flow: add a ViewBoard by IP address."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback

from .api import ViewBoardClient, ViewBoardConnectionError
from .const import CONF_MAC, CONF_SEARCH_NETWORKS, DOMAIN
from .discovery import parse_network


async def _probe(host: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return (device info, error key)."""
    try:
        info = await ViewBoardClient(host).get_device_info()
    except ViewBoardConnectionError:
        return None, "cannot_connect"
    if info.get("power") is None:
        return None, "not_viewboard"
    return info, None


def _entry_data(host: str, info: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_HOST: host,
        CONF_MAC: info.get("mac"),
        "model": info.get("model"),
        "serial": info.get("serial"),
        "firmware": info.get("firmware"),
    }


class ViewBoardConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ViewBoardOptionsFlow:
        return ViewBoardOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            info, error = await _probe(host)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(info.get("serial") or info.get("mac") or host)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                model = (info.get("model") or "ViewBoard").removesuffix("_CT2")
                title = user_input.get(CONF_NAME, "").strip() or f"{model} ({host})"
                return self.async_create_entry(title=title, data=_entry_data(host, info))

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_HOST): str, vol.Optional(CONF_NAME): str}),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the IP address of an existing board."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            info, error = await _probe(host)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(info.get("serial") or info.get("mac") or host)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates=_entry_data(host, info))

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}),
            errors=errors,
        )


class ViewBoardOptionsFlow(OptionsFlow):
    """Extra networks to search when a board's IP changes (for boards behind a router)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = ", ".join(self.config_entry.options.get(CONF_SEARCH_NETWORKS, []))
        if user_input is not None:
            current = user_input.get(CONF_SEARCH_NETWORKS, "")
            networks = []
            for text in current.replace(",", " ").split():
                try:
                    networks.append(str(parse_network(text)))
                except ValueError:
                    errors[CONF_SEARCH_NETWORKS] = "invalid_network"
                    break
            if not errors:
                return self.async_create_entry(data={CONF_SEARCH_NETWORKS: list(dict.fromkeys(networks))})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Optional(CONF_SEARCH_NETWORKS, default=current): str}),
            errors=errors,
        )
