"""Smoke test: generate demo data and print sensors/rates (dev only)."""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))

import stubs  # noqa: F401,E402

from custom_components.bkw_dynamic_tariffs.models import (  # noqa: E402
    build_demo_data,
    build_forecast_attribute,
    build_rates,
)

data = build_demo_data("seeland-mittelland", 20.0, 40.0)
now = datetime.now(tz=timezone.utc)
print("source:", data.source, "| region:", data.region)
for w in data.windows:
    print(" ", w.date, w.level.value, w.discount_pct, "%", "active:", w.is_active(now))
print("current discount:", data.current_discount_pct(now), "%")
print("rates:", json.dumps(build_rates(data, now, 25.0))[:300])
print("forecast[0]:", json.dumps(build_forecast_attribute(data, now)[0]))
