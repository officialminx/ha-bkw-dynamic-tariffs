<div align="center">

# ☀️ BKW Dynamic Tariffs for Home Assistant

**Custom integration for BKW's dynamic grid usage tariff «Sonne scheint»**

Sunshine discount windows as Home Assistant sensors — ready for
Predbat, EVCC & automations.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-v0.0.1--beta-orange)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.11%2B-038FC7)
![Platform](https://img.shields.io/badge/platform-sensor%20%7C%20binary__sensor-lightgrey)

[Installation](#-installation) · [Configuration](#-configuration) · [Entities](#-entities) · [Support](#-community--support)

</div>

---

> [!IMPORTANT]
> **Pre-release (v0.0.1).** BKW plans to launch the tariff in 2027 and the
> public **EMS API endpoint is not published yet**. The integration is built
> so that only the endpoint URL needs to be adjusted once BKW documents it.
> Until then, use the built-in **demo mode** to explore all entities.

## ✨ Features

- 📊 **Current discount sensor** — live discount in % with a JSON forecast
  attribute for today + tomorrow
- 🏷️ **Discount level sensor** — announced level `none` / `medium` / `high`
  for today (published bindingly at 17:00 the day before)
- 💰 **Net usage tariff sensor** — effective grid tariff in Rp./kWh with a
  **Predbat-compatible `rates` attribute** (`[{from, to, value}]`)
- 🔛 **Binary sensor** — ON while a discount window is active
  (daily 13:00–17:00, April–September, Europe/Zurich)
- 🗺️ **All 5 BKW regions** — Jura, Seeland-Mittelland, Emmental-Oberaargau,
  Oberland West, Oberland Ost
- 🔐 **API-key first** — subscription key sent as `Ocp-Apim-Subscription-Key`,
  stored securely in the config entry (never in `configuration.yaml`)
- ⏰ **Gentle polling** — one fetch per day at 17:05 (after BKW's publication
  time) plus two retries; deliberately **no hourly polling**
- 🧪 **Demo mode** — deterministic sample data without any API access
- 🌍 **Translations** — English, German, French

## 📖 How the tariff works

| Property | Value |
| --- | --- |
| Discount window | daily **13:00–17:00** (Europe/Zurich) |
| Season | **April – September** |
| Levels | `medium` (≥ 50% sunshine in window) / `high` (≥ 80%) |
| Max. discount | **40%** on the energy part of the grid usage tariff |
| Publication | **binding at 17:00 the day before** (bkw.ch + EMS API) |
| Regions | Jura (Delémont), Seeland-Mittelland (Zollikofen), Emmental-Oberaargau (Koppigen), Oberland West (Frutigen), Oberland Ost (Meiringen) |

Source: official BKW technical description — <https://www.bkw.ch/sonnescheint>

## 📦 Installation

### HACS (recommended)

1. Make sure [HACS](https://hacs.xyz) is installed
2. HACS → ⋮ (top right) → **Custom repositories**
3. Add this repository URL with category **Integration**
4. Search for & install **"BKW Dynamic Tariffs"**
5. Restart Home Assistant

### Manual

1. Download and copy the `custom_components/bkw_dynamic_tariffs/` folder
   into the `custom_components/` directory of your Home Assistant
   configuration
2. Restart Home Assistant

## ⚙️ Configuration

Settings → **Devices & Services** → **Add Integration** → search for
**BKW Dynamic Tariffs**

| Field | Description |
| --- | --- |
| **Region** | Your BKW tariff region (dropdown, see table above) |
| **API key** | Subscription key, sent as `Ocp-Apim-Subscription-Key` header *(not required in demo mode)* |
| **API endpoint** | Full URL of the EMS discount-window endpoint. The default is a **placeholder** — replace it once BKW publishes the official URL |
| **Base tariff** *(optional)* | Your grid usage energy tariff in Rp./kWh; enables the net tariff sensor with `rates` |
| **Medium / High discount %** | Discount per level (defaults 20% / 40%; BKW specifies a 40% maximum) |
| **Demo mode** | Deterministic sample data without API access |

Changes later: integration entry → **Configure** (reconfigure) or the
reauth dialog is started automatically if the API key is rejected.

Manuelle Aktualisierung: Service `bkw_dynamic_tariffs.refresh`.

## 🛠️ Entities

| Entity | Description |
| --- | --- |
| `sensor.bkw_sonne_scheint_current_discount` | Currently granted discount in `%` (0 outside the window) |
| `sensor.bkw_sonne_scheint_discount_level_today` | Announced level for today: `none` / `medium` / `high` |
| `sensor.bkw_sonne_scheint_net_usage_tariff` | Effective usage tariff in Rp./kWh with `rates` *(only if base tariff configured)* |
| `binary_sensor.bkw_sonne_scheint_discount_window_active` | ON while a discount window is active |

All entities belong to one device per config entry (per region).

### Forecast attribute (`data`)

```json
[
  {
    "date": "2027-07-14",
    "level": "high",
    "discount_percent": 40.0,
    "window_start": "2027-07-14T13:00:00+02:00",
    "window_end": "2027-07-14T17:00:00+02:00",
    "region": "seeland-mittelland"
  }
]
```

Entries without an announcement use `"level": "none"` and
`"announced": false`.

### Predbat-style `rates` attribute

```json
[
  { "from": "2027-07-14T00:00:00+02:00", "to": "2027-07-14T13:00:00+02:00", "value": 25.0 },
  { "from": "2027-07-14T13:00:00+02:00", "to": "2027-07-14T17:00:00+02:00", "value": 15.0 },
  { "from": "2027-07-14T17:00:00+02:00", "to": "2027-07-15T00:00:00+02:00", "value": 25.0 }
]
```

Values in **Rp./kWh** (`rates_unit` attribute); contiguous segments for
today + tomorrow. Rescale for your optimizer if it expects a different unit.

## 🤖 Example automation

```yaml
automation:
  - alias: "Waschmaschine bei Sonne-Rabatt"
    trigger:
      - platform: state
        entity_id: binary_sensor.bkw_sonne_scheint_discount_window_active
        to: "on"
    condition:
      - condition: numeric_state
        entity_id: sensor.bkw_sonne_scheint_current_discount
        above: 19
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.washing_machine
```

## 🔑 Getting an API key

The official EMS interface (per BKW's technical description, Anhang 7.1)
will provide the discount announcements. The key is sent as an
`Ocp-Apim-Subscription-Key` header (Azure API Management style). Once BKW
publishes developer documentation (expected at tariff launch or on request
via bkw.ch), update the **API endpoint** field via *Configure* — no code
change required.

## ❓ FAQ / Troubleshooting

**Entities show `unknown` after setup** — In non-demo mode the API endpoint
URL must point to the (future) BKW EMS endpoint; until then use demo mode.

**No data for tomorrow after 17:05** — The integration retries at 18:05 and
19:05 automatically. Check the integration's logs (`custom_components.bkw_dynamic_tariffs`).

**Wrong region?** — Reconfigure the entry and pick the correct region; or
create one entry per region if you monitor several.

Enable debug logging:

```yaml
logger:
  logs:
    custom_components.bkw_dynamic_tariffs: debug
```

## 💻 Development

```bash
python3 -m unittest discover -s tests -v   # unit tests (stdlib only)
python3 -m compileall custom_components    # syntax check
python3 scripts/demo_smoke.py              # demo data smoke test
```

The parsing/window logic lives in `models.py` without any Home Assistant
imports, so it stays easily testable. Contributions welcome — please open
an issue first to discuss your idea.

## ❤️ Community & Support

- 🐛 Found a bug or have a feature request?
  [Open an issue](https://github.com/officialminx/ha-bkw-dynamic-tariffs/issues)
- 💬 Questions? [Start a discussion](https://github.com/officialminx/ha-bkw-dynamic-tariffs/discussions)
- ⭐ If this integration helps you, a star is appreciated!

<a href="https://www.buymeacoffee.com/" target="_blank">☕</a>

## ⚠️ Disclaimer

This project is not affiliated with or endorsed by BKW Energie AG.
Tariff details may change until the official launch — verify parameters
(discounts, window times, season) against the official BKW documentation:
<https://www.bkw.ch/sonnescheint>

## 📄 License

This project is licensed under the [MIT License](LICENSE).
