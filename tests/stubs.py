"""Minimal module stubs so tests can import the integration package.

Only used when the tests run outside of a Home Assistant environment
(the real modules win if already importable).
"""
from __future__ import annotations

import sys
import types
from datetime import datetime, timezone


def _module(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


def _install() -> None:
    try:  # pragma: no cover - real environment available
        import voluptuous  # noqa: F401

        return
    except ImportError:
        pass

    # --- voluptuous -------------------------------------------------------
    voluptuous = _module("voluptuous")

    class _Marker:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def __call__(self, *args, **kwargs):
            return _Marker(*args, **kwargs)

    voluptuous.Schema = lambda *a, **k: (a[0] if a else None)
    for marker in ("Required", "Optional", "In", "Coerce", "All"):
        setattr(voluptuous, marker, _Marker())

    # --- aiohttp ----------------------------------------------------------
    aiohttp = _module("aiohttp")
    aiohttp.ClientSession = type("ClientSession", (), {})
    aiohttp.ClientError = type("ClientError", (Exception,), {})
    aiohttp.ClientTimeout = lambda **kwargs: kwargs

    # --- homeassistant ----------------------------------------------------
    _module("homeassistant")

    config_entries = _module("homeassistant.config_entries")
    config_entries.ConfigEntry = type("ConfigEntry", (), {})

    const = _module("homeassistant.const")
    const.Platform = type("Platform", (), {"SENSOR": "sensor", "BINARY_SENSOR": "binary_sensor"})

    core = _module("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})
    core.ServiceCall = type("ServiceCall", (), {})
    core.callback = lambda func: func

    _module("homeassistant.helpers")
    aiohttp_client = _module("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda hass: None

    _module("homeassistant.helpers.config_validation")

    event = _module("homeassistant.helpers.event")
    event.async_call_later = lambda *a, **k: lambda: None
    event.async_track_time_change = lambda *a, **k: lambda: None

    class _DataUpdateCoordinator:
        def __init__(self, hass, logger, *, name=None, update_interval=None):
            self.hass = hass
            self.name = name
            self.data = None
            self.last_update_success = False

        async def async_shutdown(self):  # pragma: no cover
            pass

        async def async_refresh(self):  # pragma: no cover
            pass

    update_coordinator = _module("homeassistant.helpers.update_coordinator")
    update_coordinator.DataUpdateCoordinator = _DataUpdateCoordinator
    update_coordinator.ConfigEntryAuthFailed = type(
        "ConfigEntryAuthFailed", (Exception,), {}
    )
    update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})

    util = _module("homeassistant.util")
    dt = _module("homeassistant.util.dt")
    dt.utcnow = lambda: datetime.now(tz=timezone.utc)
    util.dt = dt


_install()
