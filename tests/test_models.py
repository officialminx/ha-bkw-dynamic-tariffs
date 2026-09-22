"""Unit tests for the pure logic in models.py (no Home Assistant needed)."""
from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import stubs  # noqa: F401,E402  (installs HA/voluptuous stubs if needed)

from custom_components.bkw_dynamic_tariffs.models import (  # noqa: E402
    BkwTariffData,
    DiscountLevel,
    DiscountWindow,
    build_demo_data,
    build_forecast_attribute,
    build_rates,
    demo_level_for,
    parse_level,
    parse_windows_payload,
)


UTC = timezone.utc


def window(day, level, pct=40.0):
    return DiscountWindow(
        date=date.fromisoformat(day),
        level=level,
        discount_pct=pct,
        region="seeland-mittelland",
    )


class ParseLevelTests(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(parse_level("HIGH"), DiscountLevel.HIGH)
        self.assertEqual(parse_level("high"), DiscountLevel.HIGH)
        self.assertEqual(parse_level("Hoch"), DiscountLevel.HIGH)
        self.assertEqual(parse_level("mittel"), DiscountLevel.MEDIUM)
        self.assertEqual(parse_level("M"), DiscountLevel.MEDIUM)
        self.assertEqual(parse_level("0"), DiscountLevel.NONE)
        self.assertEqual(parse_level("kein"), DiscountLevel.NONE)

    def test_numeric(self):
        self.assertEqual(parse_level(0), DiscountLevel.NONE)
        self.assertEqual(parse_level(1), DiscountLevel.MEDIUM)
        self.assertEqual(parse_level(2), DiscountLevel.HIGH)

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            parse_level(None)


class ParsePayloadTests(unittest.TestCase):
    def test_camel_case_payload(self):
        payload = {
            "region": "seeland-mittelland",
            "publishedAt": "2027-07-13T17:00:00+02:00",
            "discountWindows": [
                {"date": "2027-07-14", "level": "HIGH", "discountPercent": 40},
                {"date": "2027-07-15", "level": "MEDIUM"},
            ],
        }
        data = parse_windows_payload(payload, "jura", 20.0, 40.0)
        self.assertEqual(data.region, "seeland-mittelland")
        self.assertEqual(
            data.published_at, datetime.fromisoformat("2027-07-13T17:00:00+02:00")
        )
        self.assertEqual(len(data.windows), 2)
        self.assertEqual(data.windows[0].level, DiscountLevel.HIGH)
        self.assertEqual(data.windows[0].discount_pct, 40.0)
        # No pct for medium -> configured default applies
        self.assertEqual(data.windows[1].discount_pct, 20.0)

    def test_snake_case_list_payload(self):
        payload = [
            {"datum": "2027-07-14", "rabattstufe": "hoch"},
            {"day": "2027-07-15", "level": 0},
        ]
        data = parse_windows_payload(payload, "jura", 20.0, 40.0)
        self.assertEqual(len(data.windows), 2)
        self.assertEqual(data.windows[0].level, DiscountLevel.HIGH)
        self.assertEqual(data.windows[0].discount_pct, 40.0)
        self.assertEqual(data.windows[1].level, DiscountLevel.NONE)

    def test_fraction_percent(self):
        payload = [{"date": "2027-07-14", "discount": 0.2}]
        data = parse_windows_payload(payload, "jura", 20.0, 40.0)
        self.assertEqual(data.windows[0].discount_pct, 20.0)
        self.assertEqual(data.windows[0].level, DiscountLevel.MEDIUM)

    def test_level_derived_from_pct(self):
        payload = [{"date": "2027-07-14", "discountPercent": 45}]
        data = parse_windows_payload(payload, "jura", 20.0, 40.0)
        self.assertEqual(data.windows[0].level, DiscountLevel.HIGH)

    def test_invalid_items_skipped(self):
        payload = [
            {"level": "HIGH"},  # no date
            {"date": "2027-07-14", "level": "HIGH"},
            "garbage",
        ]
        data = parse_windows_payload(payload, "jura", 20.0, 40.0)
        self.assertEqual(len(data.windows), 1)

    def test_none_payload_raises(self):
        with self.assertRaises(ValueError):
            parse_windows_payload(None, "jura", 20.0, 40.0)


class WindowBoundaryTests(unittest.TestCase):
    """Window: 13:00-17:00 Europe/Zurich (= 11:00-15:00 UTC in summer)."""

    def setUp(self):
        self.data = BkwTariffData(
            region="seeland-mittelland",
            windows=[window("2027-07-14", DiscountLevel.HIGH, 40.0)],
        )

    def test_before_window(self):
        # 12:59 Zurich summer time == 10:59 UTC
        now = datetime(2027, 7, 14, 10, 59, tzinfo=UTC)
        self.assertFalse(self.data.active_window(now))
        self.assertEqual(self.data.current_discount_pct(now), 0.0)

    def test_window_start_inclusive(self):
        # 13:00 Zurich summer time == 11:00 UTC
        now = datetime(2027, 7, 14, 11, 0, tzinfo=UTC)
        self.assertTrue(self.data.active_window(now))
        self.assertEqual(self.data.current_discount_pct(now), 40.0)

    def test_window_end_exclusive(self):
        # 17:00 Zurich summer time == 15:00 UTC
        now = datetime(2027, 7, 14, 15, 0, tzinfo=UTC)
        self.assertFalse(self.data.active_window(now))

    def test_next_window_future(self):
        now = datetime(2027, 7, 14, 9, 0, tzinfo=UTC)
        nxt = self.data.next_window(now)
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.date, date(2027, 7, 14))

    def test_next_window_none_when_past(self):
        now = datetime(2027, 7, 14, 16, 0, tzinfo=UTC)
        self.assertIsNone(self.data.next_window(now))

    def test_window_outside_season_ignored_for_tomorrow(self):
        # 30 September -> tomorrow (Oct 1) is out of season
        data = BkwTariffData(
            region="jura",
            windows=[window("2027-09-30", DiscountLevel.MEDIUM, 20.0)],
        )
        now = datetime(2027, 9, 29, 20, 0, tzinfo=UTC)
        self.assertFalse(data.missing_tomorrow(now))

    def test_missing_tomorrow_in_season(self):
        # 12 July 18:00 Zurich -> tomorrow is 13 July (no window announced)
        now = datetime(2027, 7, 12, 16, 0, tzinfo=UTC)
        self.assertTrue(self.data.missing_tomorrow(now))


class RatesTests(unittest.TestCase):
    def test_rates_high_discount_today(self):
        data = BkwTariffData(
            region="seeland-mittelland",
            windows=[window("2027-07-14", DiscountLevel.HIGH, 40.0)],
        )
        now = datetime(2027, 7, 14, 6, 0, tzinfo=UTC)
        rates = build_rates(data, now, 25.0)
        # Today: base / discount / base; tomorrow (no discount) merges with
        # today's evening segment across midnight -> 3 contiguous segments.
        self.assertEqual(len(rates), 3)
        self.assertEqual(
            [r["value"] for r in rates],
            [25.0, 15.0, 25.0],
        )
        self.assertEqual(rates[0]["from"], "2027-07-14T00:00:00+02:00")
        self.assertEqual(rates[1]["from"], "2027-07-14T13:00:00+02:00")
        self.assertEqual(rates[1]["to"], "2027-07-14T17:00:00+02:00")
        self.assertEqual(rates[2]["from"], "2027-07-14T17:00:00+02:00")
        # Merged across midnight up to end of tomorrow
        self.assertEqual(rates[2]["to"], "2027-07-16T00:00:00+02:00")

    def test_rates_merge_without_discount(self):
        data = BkwTariffData(region="seeland-mittelland", windows=[])
        now = datetime(2027, 7, 14, 6, 0, tzinfo=UTC)
        rates = build_rates(data, now, 25.0)
        # Both days are flat base tariff -> one contiguous segment
        self.assertEqual(len(rates), 1)
        self.assertEqual(rates[0]["value"], 25.0)
        self.assertEqual(rates[0]["from"], "2027-07-14T00:00:00+02:00")
        self.assertEqual(rates[0]["to"], "2027-07-16T00:00:00+02:00")


class ForecastAttributeTests(unittest.TestCase):
    def test_announced_and_unannounced_days(self):
        data = BkwTariffData(
            region="seeland-mittelland",
            windows=[window("2027-07-14", DiscountLevel.HIGH, 40.0)],
        )
        now = datetime(2027, 7, 14, 6, 0, tzinfo=UTC)
        forecast = build_forecast_attribute(data, now)
        self.assertEqual(len(forecast), 2)
        self.assertEqual(forecast[0]["level"], "high")
        self.assertNotIn("announced", forecast[0])
        self.assertEqual(forecast[1]["level"], "none")
        self.assertFalse(forecast[1]["announced"])


class DemoDataTests(unittest.TestCase):
    def test_deterministic(self):
        day = date(2027, 7, 20)
        first = demo_level_for(day, "jura")
        second = demo_level_for(day, "jura")
        self.assertEqual(first, second)

    def test_out_of_season_is_none(self):
        self.assertEqual(demo_level_for(date(2027, 1, 15), "jura"), DiscountLevel.NONE)
        self.assertEqual(demo_level_for(date(2027, 12, 5), "jura"), DiscountLevel.NONE)

    def test_demo_data_structure(self):
        data = build_demo_data("jura", 20.0, 40.0)
        self.assertEqual(data.source, "demo")
        self.assertEqual(len(data.windows), 3)
        for w in data.windows:
            if w.level is DiscountLevel.MEDIUM:
                self.assertEqual(w.discount_pct, 20.0)
            elif w.level is DiscountLevel.HIGH:
                self.assertEqual(w.discount_pct, 40.0)
            else:
                self.assertEqual(w.discount_pct, 0.0)


if __name__ == "__main__":
    unittest.main()
