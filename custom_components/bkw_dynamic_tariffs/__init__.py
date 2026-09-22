"""The BKW Dynamic Tariffs («Sonne scheint») Home Assistant integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BkwApiClient, BkwDemoClient
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_DEMO_MODE,
    CONF_HIGH_DISCOUNT_PCT,
    CONF_MEDIUM_DISCOUNT_PCT,
    CONF_REGION,
    DEFAULT_HIGH_DISCOUNT_PCT,
    DEFAULT_MEDIUM_DISCOUNT_PCT,
    DOMAIN,
)
from .coordinator import BkwTariffCoordinator
from .exceptions import BkwTariffError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

SERVICE_REFRESH = "refresh"
SERVICE_REFRESH_SCHEMA = vol.Schema({})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register integration-level services."""

    async def _handle_refresh(call: ServiceCall) -> None:
        entries = hass.data.get(DOMAIN, {})
        for entry_data in entries.values():
            coordinator: BkwTariffCoordinator = entry_data["coordinator"]
            await coordinator.async_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, _handle_refresh, schema=SERVICE_REFRESH_SCHEMA
    )
    return True


def _build_client(hass: HomeAssistant, entry: ConfigEntry) -> Any:
    """Create the API client (real or demo) for a config entry."""
    data = entry.data
    region = data[CONF_REGION]
    medium_pct = float(data.get(CONF_MEDIUM_DISCOUNT_PCT, DEFAULT_MEDIUM_DISCOUNT_PCT))
    high_pct = float(data.get(CONF_HIGH_DISCOUNT_PCT, DEFAULT_HIGH_DISCOUNT_PCT))

    if data.get(CONF_DEMO_MODE):
        return BkwDemoClient(region, medium_pct=medium_pct, high_pct=high_pct)
    return BkwApiClient(
        session=async_get_clientsession(hass),
        api_key=data[CONF_API_KEY],
        base_url=data.get(CONF_BASE_URL, ""),
        region=region,
        medium_pct=medium_pct,
        high_pct=high_pct,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BKW Dynamic Tariffs from a config entry."""
    coordinator = BkwTariffCoordinator(hass, _build_client(hass, entry))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    try:
        await coordinator.async_config_entry_first_refresh()
    except BkwTariffError as err:  # pragma: no cover - defensive
        _LOGGER.error("Initial data fetch failed: %s", err)
        hass.data[DOMAIN].pop(entry.entry_id)
        return False

    coordinator.async_start_schedule()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its data changes (reconfigure)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and cancel coordinator timers."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if entry_data is not None:
        coordinator: BkwTariffCoordinator = entry_data["coordinator"]
        await coordinator.async_shutdown()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries (currently only version 1 exists)."""
    return True
