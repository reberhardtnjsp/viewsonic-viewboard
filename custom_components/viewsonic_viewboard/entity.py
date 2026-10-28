"""Base entity for ViewBoard entities."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DOMAIN
from .coordinator import ViewBoardCoordinator


class ViewBoardEntity(CoordinatorEntity[ViewBoardCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ViewBoardCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        model = (entry.data.get("model") or "ViewBoard").removesuffix("_CT2")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            connections={(CONNECTION_NETWORK_MAC, mac)} if (mac := entry.data.get(CONF_MAC)) else set(),
            manufacturer="ViewSonic",
            model=model,
            name=entry.title,
            serial_number=entry.data.get("serial"),
            sw_version=entry.data.get("firmware"),
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.get("online", False)
