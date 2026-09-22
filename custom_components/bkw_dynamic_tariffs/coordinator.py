"""DataUpdateCoordinator for the BKW Dynamic Tariffs integration.

BKW publishes the binding discount level for the *next* day at 17:00
local time (Europe/Zurich). Therefore the coordinator refreshes once per
day shortly after 17:05 instead of polling hourly. If the announcement
for tomorrow is still missing, up to two retries are scheduled
(18:05 and 19:05).
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Callable, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_change
from homeassistant.helpers.update_coordinator import (
    ConfigEntryAuthFailed,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PUBLISH_HOUR, RETRY_DELTAS_HOURS, UPDATE_MINUTE
from .exceptions import BkwAuthError, BkwTariffError
from .models import BkwTariffData

_LOGGER = logging.getLogger(__name__)


class BkwTariffCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches BKW discount window announcements."""

    def __init__(self, hass: HomeAssistant, client: Any) -> None:
        """Initialize the coordinator.

        `client` is a :class:`~.api.BkwApiClient` or
        :class:`~.api.BkwDemoClient` (not imported to avoid a circular
        import) and must provide ``async_get_data()``.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # scheduled manually, see async_start_schedule
        )
        self.client = client
        self._retry_index = 0
        self._unsub_daily: Optional[Callable[[], None]] = None
        self._unsub_retry: Optional[Callable[[], None]] = None

    async def _async_update_data(self) -> BkwTariffData:
        """Fetch the latest announcements from the BKW API (or demo)."""
        try:
            data = await self.client.async_get_data()
        except BkwAuthError as err:
            # Surfaced by HA as "authentication error" -> starts reauth flow.
            raise ConfigEntryAuthFailed from err
        except BkwTariffError as err:
            raise UpdateFailed(str(err)) from err

        self._retry_index = 0
        return data

    def async_start_schedule(self) -> None:
        """Register the daily update timer (call after first refresh)."""
        self._unsub_daily = async_track_time_change(
            self.hass,
            self._async_timer_fired,
            hour=PUBLISH_HOUR,
            minute=UPDATE_MINUTE,
            second=0,
        )

    @callback
    def _async_timer_fired(self, now: Any) -> None:
        self.hass.async_create_task(self._async_refresh_and_check())

    async def _async_refresh_and_check(self) -> None:
        """Refresh data and schedule retries if tomorrow is missing."""
        await self.async_refresh()
        now = dt_util.utcnow()
        if self.last_update_success and self.data is not None:
            if self.data.missing_tomorrow(now):
                self._schedule_retry()

    def _schedule_retry(self) -> None:
        if self._retry_index >= len(RETRY_DELTAS_HOURS):
            _LOGGER.warning(
                "No announcement for tomorrow received from the BKW API; "
                "giving up until the next daily update (17:05)"
            )
            return
        delay = timedelta(hours=RETRY_DELTAS_HOURS[self._retry_index])
        self._retry_index += 1
        _LOGGER.info(
            "Announcement for tomorrow missing; scheduling retry in %s h", delay
        )
        if self._unsub_retry is not None:
            self._unsub_retry()
        self._unsub_retry = async_call_later(
            self.hass, delay, self._async_timer_fired
        )

    async def async_shutdown(self) -> None:
        """Cancel timers when the entry is unloaded."""
        if self._unsub_daily is not None:
            self._unsub_daily()
            self._unsub_daily = None
        if self._unsub_retry is not None:
            self._unsub_retry()
            self._unsub_retry = None
        await super().async_shutdown()
