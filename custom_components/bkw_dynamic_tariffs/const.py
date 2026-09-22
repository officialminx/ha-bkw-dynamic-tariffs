"""Constants for the BKW Dynamic Tariffs («Sonne scheint») integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "bkw_dynamic_tariffs"
MANUFACTURER: Final = "BKW Energie AG"

# --- Config entry keys -----------------------------------------------------
CONF_API_KEY: Final = "api_key"
CONF_BASE_URL: Final = "base_url"
CONF_REGION: Final = "region"
CONF_BASE_TARIFF_RP: Final = "base_tariff_rp"
CONF_MEDIUM_DISCOUNT_PCT: Final = "medium_discount_pct"
CONF_HIGH_DISCOUNT_PCT: Final = "high_discount_pct"
CONF_DEMO_MODE: Final = "demo_mode"

# --- Tariff model (source: official BKW «Sonne scheint» technical document) -
# Discount window: April to September, daily 13:00-17:00 (Europe/Zurich).
# Two discount levels: medium (>= 50% sunshine duration in the 4h window)
# and high (>= 80%). Maximum discount: 40% on the grid usage energy tariff.
WINDOW_START_HOUR: Final = 13
WINDOW_END_HOUR: Final = 17
DISCOUNT_MONTHS: Final = frozenset({4, 5, 6, 7, 8, 9})

TIMEZONE: Final = "Europe/Zurich"

# BKW publishes the discount level for the *next* day at 17:00 local time.
PUBLISH_HOUR: Final = 17
UPDATE_MINUTE: Final = 5
RETRY_DELTAS_HOURS: Final = (1, 2)

# Default discount percentages per level (the official document only states
# the maximum of 40%; exact per-region values may be published later).
DEFAULT_MEDIUM_DISCOUNT_PCT: Final = 20.0
DEFAULT_HIGH_DISCOUNT_PCT: Final = 40.0

# Default EMS API endpoint. The exact public EMS API URL of BKW is not yet
# documented publicly; override it in the config flow once known.
DEFAULT_BASE_URL: Final = "https://api.bkw.ch/api/sonne-scheint/v1/discount-windows"

# --- Tariff regions (BKW supply area split into five regions) ---------------
REGIONS: Final = {
    "jura": "Jura (Referenzstation Delémont)",
    "seeland-mittelland": "Seeland-Mittelland (Referenzstation Zollikofen)",
    "emmental-oberaargau": "Emmental-Oberaargau (Referenzstation Koppigen)",
    "oberland-west": "Oberland West (Referenzstation Frutigen)",
    "oberland-ost": "Oberland Ost (Referenzstation Meiringen)",
}

# --- Misc -------------------------------------------------------------------
SUBSCRIPTION_HEADER: Final = "Ocp-Apim-Subscription-Key"
USER_AGENT: Final = "ha-bkw-dynamic-tariffs/0.1.0 (Home Assistant custom integration)"
