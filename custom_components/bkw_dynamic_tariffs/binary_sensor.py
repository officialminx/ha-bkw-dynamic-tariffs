"""Binary sensor platform for the BKW Dynamic Tariffs integration."""
from __future__ import annotations

from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import BkwTariffCoordinator
from .sensor import BkwEntity


class BkwWindowActiveSensor(BkwEntity, BinarySensorEntity):
    """ON while a discount window is currently active (13:00-17:00)."""

    _attr_name = "Discount window active"
    _attr_icon = "mdi:weather-sunny"

    def __init__(
        self, coordinator: BkwTariffCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "window_active")

    @property
    def is_on(self) -> bool:
        data = self._data
        if data is None:
            return False
        return data.active_window(dt_util.utcnow()) is not None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = self._data
        if data is None:
            return {}
        now = dt_util.utcnow()
        window = data.active_window(now)
        if window is None:
            next_window = data.next_window(now)
            return {
                "region": data.region,
                "level": next_window.level.value if next_window else "none",
                "discount_percent": round(next_window.discount_pct, 1)
                if next_window
                else 0.0,
                "until": None,
                "next_start": next_window.window_start.isoformat()
                if next_window
                else None,
                "source": data.source,
            }
        return {
            "region": data.region,
            "level": window.level.value,
            "discount_percent": round(window.discount_pct, 1),
            "until": window.window_end.isoformat(),
            "next_start": None,
            "source": data.source,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the discount window binary sensor."""
    coordinator: BkwTariffCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    async_add_entities([BkwWindowActiveSensor(coordinator, entry)])
