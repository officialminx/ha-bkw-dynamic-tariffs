"""Data models and pure logic for the BKW «Sonne scheint» tariffs.

This module intentionally has **no Home Assistant imports** so that the
parsing/window/rate logic can be unit-tested with plain Python.

Tariff model (from the official BKW technical description):
    * Dynamic grid usage tariff («Netznutzungstarif») with discount windows.
    * Window: April to September, daily 13:00-17:00 Europe/Zurich.
    * Two levels: medium (>=50% sunshine in the 4h window) and
      high (>=80%), max. discount 40% on the energy part of the grid tariff.
    * The binding discount level for the next day is published at 17:00
      on the previous day.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from .const import (
    DISCOUNT_MONTHS,
    WINDOW_END_HOUR,
    WINDOW_START_HOUR,
)

_LOGGER = logging.getLogger(__name__)

_ZURICH = ZoneInfo("Europe/Zurich")
_UTC = timezone.utc

# Alternative JSON keys accepted while parsing (camelCase, snake_case, DE).
_WINDOW_LIST_KEYS = ("discountWindows", "discount_windows", "windows", "data", "rabattfenster")
_DATE_KEYS = ("date", "day", "datum", "validFor", "valid_for")
_LEVEL_KEYS = ("level", "rabattstufe", "discountLevel", "discount_level", "stufe")
_PCT_KEYS = ("discountPercent", "discount_percent", "discount", "rabatt", "rabattProzent", "value")
_PUBLISHED_KEYS = ("publishedAt", "published_at", "timestamp", "publicationTime", "publication_time")
_REGION_KEYS = ("region", "regionId", "region_id")


class DiscountLevel(str, Enum):
    """Discount level of a «Sonne scheint» window."""

    NONE = "none"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def is_discount(self) -> bool:
        """Return True if this level grants a discount."""
        return self is not DiscountLevel.NONE


_LEVEL_ALIASES = {
    "none": DiscountLevel.NONE,
    "no": DiscountLevel.NONE,
    "0": DiscountLevel.NONE,
    "kein": DiscountLevel.NONE,
    "keiner": DiscountLevel.NONE,
    "aus": DiscountLevel.NONE,
    "closed": DiscountLevel.NONE,
    "medium": DiscountLevel.MEDIUM,
    "m": DiscountLevel.MEDIUM,
    "mittel": DiscountLevel.MEDIUM,
    "mittlerer rabatt": DiscountLevel.MEDIUM,
    "1": DiscountLevel.MEDIUM,
    "high": DiscountLevel.HIGH,
    "h": DiscountLevel.HIGH,
    "hoch": DiscountLevel.HIGH,
    "hoher rabatt": DiscountLevel.HIGH,
    "2": DiscountLevel.HIGH,
}


def parse_level(value: Any) -> DiscountLevel:
    """Parse a discount level from arbitrary JSON values."""
    if isinstance(value, DiscountLevel):
        return value
    if isinstance(value, bool):
        return DiscountLevel.MEDIUM if value else DiscountLevel.NONE
    if isinstance(value, (int, float)):
        try:
            return [DiscountLevel.NONE, DiscountLevel.MEDIUM, DiscountLevel.HIGH][int(value)]
        except IndexError:
            return DiscountLevel.HIGH
    if isinstance(value, str):
        key = value.strip().lower()
        if key in _LEVEL_ALIASES:
            return _LEVEL_ALIASES[key]
        if key in ("true", "yes", "ja", "offen", "open"):
            return DiscountLevel.MEDIUM
        if key in ("false", "no", "nein"):
            return DiscountLevel.NONE
    raise ValueError(f"Cannot parse discount level from {value!r}")


def _to_pct(value: Any) -> Optional[float]:
    """Convert a percentage value (0-1, 0-100 or string) to percent."""
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if 0 < num <= 1:
        return num * 100.0
    return num


def _parse_date(value: Any) -> Optional[date]:
    """Parse a date from ISO strings (date or datetime) or timestamps."""
    if isinstance(value, datetime):
        return value.astimezone(_ZURICH).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
        try:
            return datetime.fromtimestamp(int(text), tz=_UTC)
        except (ValueError, OverflowError):
            return None
    return None


@dataclass(frozen=True)
class DiscountWindow:
    """One announced discount window (one calendar day, 13:00-17:00)."""

    date: date
    level: DiscountLevel
    discount_pct: float
    region: str

    @property
    def window_start(self) -> datetime:
        """Start of the window as timezone-aware datetime (Europe/Zurich)."""
        return datetime.combine(self.date, time(WINDOW_START_HOUR, 0), tzinfo=_ZURICH)

    @property
    def window_end(self) -> datetime:
        """End of the window as timezone-aware datetime (Europe/Zurich)."""
        return datetime.combine(self.date, time(WINDOW_END_HOUR, 0), tzinfo=_ZURICH)

    def is_active(self, now_utc: datetime) -> bool:
        """Return True if `now_utc` lies within this window."""
        return self.window_start <= now_utc < self.window_end

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for entity attributes."""
        return {
            "date": self.date.isoformat(),
            "level": self.level.value,
            "discount_percent": round(self.discount_pct, 2),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "region": self.region,
        }


@dataclass
class BkwTariffData:
    """Normalized data returned by the API client / demo client."""

    region: str
    windows: List[DiscountWindow] = field(default_factory=list)
    published_at: Optional[datetime] = None
    source: str = "api"

    # -- lookups ------------------------------------------------------------
    def window_for_day(self, day: date) -> Optional[DiscountWindow]:
        """Return the announced window for a given calendar day, if any."""
        for window in self.windows:
            if window.date == day and window.level.is_discount:
                return window
        return None

    def level_for_day(self, day: date) -> DiscountLevel:
        """Return the announced level for a day (NONE if no discount)."""
        window = self.window_for_day(day)
        return window.level if window else DiscountLevel.NONE

    def today(self, now_utc: datetime) -> date:
        """Current calendar date in the tariff timezone."""
        return now_utc.astimezone(_ZURICH).date()

    def tomorrow(self, now_utc: datetime) -> date:
        return self.today(now_utc) + timedelta(days=1)

    def active_window(self, now_utc: datetime) -> Optional[DiscountWindow]:
        """Return the window that is currently active, if any."""
        today_window = self.window_for_day(self.today(now_utc))
        if today_window and today_window.is_active(now_utc):
            return today_window
        return None

    def next_window(self, now_utc: datetime) -> Optional[DiscountWindow]:
        """Return the next upcoming (or currently active) discount window."""
        current = self.active_window(now_utc)
        if current is not None:
            return current
        for window in sorted(self.windows, key=lambda w: w.date):
            if window.level.is_discount and window.window_start > now_utc:
                return window
        return None

    def current_discount_pct(self, now_utc: datetime) -> float:
        """Currently granted discount in percent (0 outside the window)."""
        window = self.active_window(now_utc)
        return window.discount_pct if window else 0.0

    def current_level(self, now_utc: datetime) -> DiscountLevel:
        window = self.active_window(now_utc)
        return window.level if window else DiscountLevel.NONE

    def missing_tomorrow(self, now_utc: datetime) -> bool:
        """True if no announcement for tomorrow exists yet (retry trigger)."""
        day = self.tomorrow(now_utc)
        in_season = day.month in DISCOUNT_MONTHS
        return in_season and self.window_for_day(day) is None


def _first_present(item: Dict[str, Any], keys: tuple) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def parse_windows_payload(
    payload: Any,
    region: str,
    medium_pct: float,
    high_pct: float,
) -> BkwTariffData:
    """Parse an arbitrary BKW API payload into :class:`BkwTariffData`.

    The exact EMS API schema is not published yet, therefore the parser
    accepts common key variants (camelCase / snake_case / German) and a
    top-level list or an object containing a list of windows.
    """
    if payload is None:
        raise ValueError("Empty API payload")

    if isinstance(payload, list):
        items = payload
        meta: Dict[str, Any] = {}
    elif isinstance(payload, dict):
        items = None
        for key in _WINDOW_LIST_KEYS:
            candidate = payload.get(key)
            if isinstance(candidate, list):
                items = candidate
                break
        if items is None:
            # Maybe the payload itself describes a single window.
            items = [payload]
        meta = payload
    else:
        raise ValueError(f"Unsupported payload type {type(payload)!r}")

    payload_region = region
    for key in _REGION_KEYS:
        if isinstance(meta.get(key), str) and meta[key]:
            payload_region = meta[key]
            break

    published_at = None
    for key in _PUBLISHED_KEYS:
        published_at = _parse_datetime(meta.get(key))
        if published_at is not None:
            break

    windows: List[DiscountWindow] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        day = None
        for key in _DATE_KEYS:
            day = _parse_date(item.get(key))
            if day is not None:
                break
        if day is None:
            _LOGGER.debug("Skipping window item without date: %s", item)
            continue

        level_raw = _first_present(item, _LEVEL_KEYS)
        if level_raw is None and _first_present(item, _PCT_KEYS) is not None:
            # No explicit level: derive one from a present discount value.
            pct_guess = _to_pct(_first_present(item, _PCT_KEYS)) or 0.0
            if pct_guess <= 0:
                level = DiscountLevel.NONE
            elif pct_guess >= high_pct:
                level = DiscountLevel.HIGH
            else:
                level = DiscountLevel.MEDIUM
        else:
            try:
                level = parse_level(level_raw)
            except ValueError:
                _LOGGER.debug("Skipping window item without parsable level: %s", item)
                continue

        pct = _to_pct(_first_present(item, _PCT_KEYS))
        if pct is None or pct <= 0:
            if level is DiscountLevel.MEDIUM:
                pct = medium_pct
            elif level is DiscountLevel.HIGH:
                pct = high_pct
            else:
                pct = 0.0

        windows.append(
            DiscountWindow(date=day, level=level, discount_pct=float(pct), region=payload_region)
        )

    return BkwTariffData(
        region=payload_region,
        windows=windows,
        published_at=published_at,
        source="api",
    )


def build_rates(
    data: BkwTariffData,
    now_utc: datetime,
    base_tariff_rp: float,
    days: int = 2,
) -> List[Dict[str, Any]]:
    """Build a Predbat-style ``rates`` list for the next `days` days.

    Format: ``[{"from": <ISO>, "to": <ISO>, "value": <Rp./kWh>}, ...]``
    with contiguous segments covering full days (00:00-24:00 local).
    """
    rates: List[Dict[str, Any]] = []
    start_day = data.today(now_utc)
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        day_start = datetime.combine(day, time(0, 0), tzinfo=_ZURICH)
        segments = [
            (day_start, datetime.combine(day, time(WINDOW_START_HOUR, 0), tzinfo=_ZURICH)),
            (
                datetime.combine(day, time(WINDOW_START_HOUR, 0), tzinfo=_ZURICH),
                datetime.combine(day, time(WINDOW_END_HOUR, 0), tzinfo=_ZURICH),
            ),
            (
                datetime.combine(day, time(WINDOW_END_HOUR, 0), tzinfo=_ZURICH),
                day_start + timedelta(days=1),
            ),
        ]
        window = data.window_for_day(day)
        discount = window.discount_pct if window else 0.0
        for seg_start, _seg_end in segments:
            if WINDOW_START_HOUR <= seg_start.hour < WINDOW_END_HOUR:
                seg_discount = discount
            else:
                seg_discount = 0.0
            value = round(base_tariff_rp * (100.0 - seg_discount) / 100.0, 2)
            rates.append(
                {
                    "from": seg_start.isoformat(),
                    "to": (_seg_end).isoformat(),
                    "value": value,
                }
            )
    return _merge_equal_rates(rates)


def _merge_equal_rates(rates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge neighbouring segments with identical values."""
    merged: List[Dict[str, Any]] = []
    for rate in rates:
        if merged and merged[-1]["value"] == rate["value"]:
            merged[-1]["to"] = rate["to"]
        else:
            merged.append(dict(rate))
    return merged


def build_forecast_attribute(
    data: BkwTariffData,
    now_utc: datetime,
    days: int = 2,
) -> List[Dict[str, Any]]:
    """Build the ``data`` forecast attribute for the next `days` days."""
    start_day = data.today(now_utc)
    forecast: List[Dict[str, Any]] = []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        window = data.window_for_day(day)
        if window is not None:
            forecast.append(window.to_dict())
        else:
            forecast.append(
                {
                    "date": day.isoformat(),
                    "level": DiscountLevel.NONE.value,
                    "discount_percent": 0.0,
                    "window_start": datetime.combine(
                        day, time(WINDOW_START_HOUR, 0), tzinfo=_ZURICH
                    ).isoformat(),
                    "window_end": datetime.combine(
                        day, time(WINDOW_END_HOUR, 0), tzinfo=_ZURICH
                    ).isoformat(),
                    "region": data.region,
                    "announced": False,
                }
            )
    return forecast


# --- Demo data --------------------------------------------------------------


def demo_level_for(day: date, region: str) -> DiscountLevel:
    """Deterministic pseudo-random demo level for a given day/region."""
    if day.month not in DISCOUNT_MONTHS:
        return DiscountLevel.NONE
    digest = hashlib.sha256(f"{day.isoformat()}|{region}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 10
    if bucket <= 4:
        return DiscountLevel.MEDIUM
    if bucket <= 7:
        return DiscountLevel.HIGH
    return DiscountLevel.NONE


def build_demo_data(region: str, medium_pct: float, high_pct: float) -> BkwTariffData:
    """Build deterministic demo data for today + the next two days."""
    now_utc = datetime.now(tz=_UTC)
    data = BkwTariffData(region=region, published_at=now_utc, source="demo")
    today = data.today(now_utc)
    for offset in (0, 1, 2):
        day = today + timedelta(days=offset)
        level = demo_level_for(day, region)
        pct = 0.0
        if level is DiscountLevel.MEDIUM:
            pct = medium_pct
        elif level is DiscountLevel.HIGH:
            pct = high_pct
        data.windows.append(
            DiscountWindow(date=day, level=level, discount_pct=pct, region=region)
        )
    return data

