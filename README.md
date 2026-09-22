# BKW Dynamic Tariffs for Home Assistant

Custom integration that exposes **BKW's dynamic grid usage tariff
«Sonne scheint»** (sun-dependent discount windows) as Home Assistant
sensors, so energy optimization tools (Predbat, EVCC, automations, …)
can consume the discount signal.

> ℹ️ BKW plans to launch this tariff in 2027. The exact public **EMS API
> endpoint is not published yet** — this integration is built so that only
> the endpoint URL has to be adjusted once BKW documents it. Until then,
> the **demo mode** lets you explore all sensors with deterministic
> sample data.

## How the tariff works

| Property | Value |
| --- | --- |
| Discount window | daily **13:00–17:00** (Europe/Zurich) |
| Season | **April – September** |
| Levels | `medium` (≥ 50% sunshine in window) / `high` (≥ 80%) |
| Max. discount | **40%** on the energy part of the grid usage tariff |
| Publication | **binding at 17:00 the day before** (bkw.ch + EMS API) |
| Regions | Jura (Delémont), Seeland-Mittelland (Zollikofen), Emmental-Oberaargau (Koppigen), Oberland West (Frutigen), Oberland Ost (Meiringen) |

## Installation

### HACS (custom repository)

1. HACS → ⋮ → *Custom repositories*
2. Add `https://github.com/janikbachmann/ha-bkw-dynamic-tariffs` (category: **Integration**)
3. Install **BKW Dynamic Tariffs**
4. Restart Home Assistant

### Manual

Copy `custom_components/bkw_dynamic_tariffs/` into the `custom_components/`
folder of your Home Assistant configuration and restart.

## Configuration

Settings → Devices & Services → Add Integration → **BKW Dynamic Tariffs**

| Field | Description |
| --- | --- |
| Region | Your BKW tariff region (see table above) |
| API key | Subscription key, sent as `Ocp-Apim-Subscription-Key` header (not required in demo mode) |
| API endpoint | Full URL of the EMS discount-window endpoint. The default is a **placeholder** – replace it once BKW publishes the official URL |
| Base tariff (Rp./kWh) | Optional: your grid usage energy tariff; enables the net tariff sensor with `rates` |
| Medium/High discount % | Discount per level (defaults 20% / 40%, max. discount per BKW spec is 40%) |
| Demo mode | Deterministic sample data without API access |

The integration refreshes data **once per day at 17:05** (shortly after
BKW's publication time) with up to two retries (18:05, 19:05) if the
announcement for the next day is missing. There is deliberately **no
hourly polling**. A manual refresh is available via the
`bkw_dynamic_tariffs.refresh` service.

## Sensors

| Entity | Description |
| --- | --- |
| `sensor.bkw_sonne_scheint_current_discount` | Currently granted discount in `%` (0 outside the window) |
| `sensor.bkw_sonne_scheint_discount_level_today` | Announced level for today: `none` / `medium` / `high` |
| `sensor.bkw_sonne_scheint_net_usage_tariff` | Effective usage tariff in Rp./kWh incl. Predbat-style `rates` (only if base tariff configured) |
| `binary_sensor.bkw_sonne_scheint_discount_window_active` | ON while a discount window is active |

### Forecast attribute (`data`)

The current discount sensor exposes today + tomorrow as JSON:

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

If a base tariff (Rp./kWh) is configured, the net usage tariff sensor
provides contiguous segments for today + tomorrow:

```json
[
  { "from": "2027-07-14T00:00:00+02:00", "to": "2027-07-14T13:00:00+02:00", "value": 25.0 },
  { "from": "2027-07-14T13:00:00+02:00", "to": "2027-07-14T17:00:00+02:00", "value": 15.0 },
  { "from": "2027-07-14T17:00:00+02:00", "to": "2027-07-15T00:00:00+02:00", "value": 25.0 }
]
```

Values are in **Rp./kWh** (`rates_unit` attribute). Adapt scaling to your
optimizer if it expects a different unit.

## Example automation

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

## Getting an API key

The official EMS interface (per BKW's technical description, Anhang 7.1)
will provide the discount announcements. The key is sent as an
`Ocp-Apim-Subscription-Key` header (Azure API Management style). As soon
as BKW publishes developer documentation (expected at tariff launch or on
request via bkw.ch), update the **API endpoint** field in the integration's
reconfigure dialog — no code change required.

## Development

```bash
python3 -m unittest discover -s tests -v   # unit tests (stdlib only)
python3 -m compileall custom_components    # syntax check
```

The parsing/window logic lives in `models.py` without any Home Assistant
imports, so it stays easily testable.

## Disclaimer

This project is not affiliated with or endorsed by BKW Energie AG.
Tariff details may change until the official launch — verify parameters
(discounts, window times, season) against the official BKW documentation:
<https://www.bkw.ch/sonnescheint>

## License

[MIT](LICENSE)
