"""Sensor platform for the BKW Dynamic Tariffs integration."""
from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BASE_TARIFF_RP,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import BkwTariffCoordinator
from .models import (
    BkwTariffData,
    DiscountWindow,
    build_forecast_attribute,
    build_rates,
)


class BkwEntity(CoordinatorEntity):
    """Base entity bound to the coordinator and the config entry device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: BkwTariffCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="BKW Sonne scheint",
            manufacturer=MANUFACTURER,
            model="Dynamischer Netznutzungstarif «Sonne scheint»",
        )

    @property
    def _data(self) -> Optional[BkwTariffData]:
        data = self.coordinator.data
        return data if isinstance(data, BkwTariffData) else None


class BkwCurrentDiscountSensor(BkwEntity, SensorEntity):
    """Currently granted discount in percent (0 outside the window)."""

    _attr_name = "Current discount"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:weather-sunny"

    def __init__(
        self, coordinator: BkwTariffCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "current_discount")

    @property
    def native_value(self) -> Optional[float]:
        data = self._data
        if data is None:
            return None
        return round(data.current_discount_pct(dt_util.utcnow()), 1)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = self._data
        if data is None:
            return {}
        now = dt_util.utcnow()
        next_window: Optional[DiscountWindow] = data.next_window(now)
        return {
            "region": data.region,
            "source": data.source,
            "published_at": data.published_at.isoformat()
            if data.published_at
            else None,
            "current_level": data.current_level(now).value,
            "today_level": data.level_for_day(data.today(now)).value,
            "tomorrow_level": data.level_for_day(data.tomorrow(now)).value,
            "window_active": data.active_window(now) is not None,
            "next_window_start": next_window.window_start.isoformat()
            if next_window
            else None,
            "next_window_end": next_window.window_end.isoformat()
            if next_window
            else None,
            "next_window_level": next_window.level.value if next_window else None,
            "next_window_discount_percent": round(next_window.discount_pct, 1)
            if next_window
            else 0.0,
            "data": build_forecast_attribute(data, now),
        }


class BkwDiscountLevelTodaySensor(BkwEntity, SensorEntity):
    """Announced discount level for today (none / medium / high)."""

    _attr_name = "Discount level today"
    _attr_icon = "mdi:tag-outline"

    def __init__(
        self, coordinator: BkwTariffCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "discount_level_today")

    @property
    def native_value(self) -> Optional[str]:
        data = self._data
        if data is None:
            return None
        return data.level_for_day(data.today(dt_util.utcnow())).value

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = self._data
        if data is None:
            return {}
        now = dt_util.utcnow()
        today_window = data.window_for_day(data.today(now))
        return {
            "region": data.region,
            "tomorrow_level": data.level_for_day(data.tomorrow(now)).value,
            "window_start": today_window.window_start.isoformat()
            if today_window
            else None,
            "window_end": today_window.window_end.isoformat()
            if today_window
            else None,
            "discount_percent": round(today_window.discount_pct, 1)
            if today_window
            else 0.0,
        }


class BkwNetUsageTariffSensor(BkwEntity, SensorEntity):
    """Effective grid usage energy tariff in Rp./kWh.

    Includes a Predbat-compatible ``rates`` attribute so energy
    optimization tools can consume the price signal directly.
    """

    _attr_name = "Net usage tariff"
    _attr_native_unit_of_measurement = "Rp./kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:transmission-tower"

    def __init__(
        self, coordinator: BkwTariffCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "net_usage_tariff")
        self._base_tariff_rp = float(entry.data.get(CONF_BASE_TARIFF_RP, 0.0))

    @property
    def native_value(self) -> Optional[float]:
        data = self._data
        if data is None or self._base_tariff_rp <= 0:
            return None
        discount = data.current_discount_pct(dt_util.utcnow())
        return round(self._base_tariff_rp * (100.0 - discount) / 100.0, 2)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = self._data
        if data is None or self._base_tariff_rp <= 0:
            return {}
        now = dt_util.utcnow()
        return {
            "base_tariff_rp_per_kwh": self._base_tariff_rp,
            "current_discount_percent": round(data.current_discount_pct(now), 1),
            "rates_unit": "Rp./kWh",
            "rates_format": "predbat",
            "rates": build_rates(data, now, self._base_tariff_rp),
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all BKW Dynamic Tariffs sensors."""
    coordinator: BkwTariffCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    entities = [
        BkwCurrentDiscountSensor(coordinator, entry),
        BkwDiscountLevelTodaySensor(coordinator, entry),
    ]
    if float(entry.data.get(CONF_BASE_TARIFF_RP, 0.0) or 0.0) > 0:
        entities.append(BkwNetUsageTariffSensor(coordinator, entry))
    async_add_entities(entities)
