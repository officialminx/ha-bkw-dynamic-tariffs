"""Config flow for the BKW Dynamic Tariffs integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_API_KEY,
    CONF_BASE_TARIFF_RP,
    CONF_BASE_URL,
    CONF_DEMO_MODE,
    CONF_HIGH_DISCOUNT_PCT,
    CONF_MEDIUM_DISCOUNT_PCT,
    CONF_REGION,
    DEFAULT_BASE_URL,
    DEFAULT_HIGH_DISCOUNT_PCT,
    DEFAULT_MEDIUM_DISCOUNT_PCT,
    DOMAIN,
    REGIONS,
)

_LOGGER = logging.getLogger(__name__)

ERROR_INVALID_API_KEY = "invalid_api_key"
ERROR_INVALID_URL = "invalid_url"
ERROR_INVALID_TARIFF = "invalid_tariff"
ERROR_INVALID_DISCOUNTS = "invalid_discounts"


def _region_schema(defaults: Optional[Dict[str, Any]] = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_REGION, default=defaults.get(CONF_REGION, "seeland-mittelland")
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=key, label=label)
                        for key, label in REGIONS.items()
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_API_KEY,
                default=defaults.get(CONF_API_KEY, ""),
            ): str,
            vol.Required(
                CONF_BASE_URL, default=defaults.get(CONF_BASE_URL, DEFAULT_BASE_URL)
            ): str,
            vol.Optional(
                CONF_BASE_TARIFF_RP,
                description={
                    "suggested_value": defaults.get(CONF_BASE_TARIFF_RP, 20.0)
                },
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=200, step=0.1, unit_of_measurement="Rp./kWh"
                )
            ),
            vol.Optional(
                CONF_MEDIUM_DISCOUNT_PCT,
                default=defaults.get(
                    CONF_MEDIUM_DISCOUNT_PCT, DEFAULT_MEDIUM_DISCOUNT_PCT
                ),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
            ),
            vol.Optional(
                CONF_HIGH_DISCOUNT_PCT,
                default=defaults.get(
                    CONF_HIGH_DISCOUNT_PCT, DEFAULT_HIGH_DISCOUNT_PCT
                ),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
            ),
            vol.Required(
                CONF_DEMO_MODE, default=defaults.get(CONF_DEMO_MODE, False)
            ): BooleanSelector(),
        }
    )


def _validate(user_input: Dict[str, Any]) -> Dict[str, str]:
    """Validate user input; returns a dict of field -> error key."""
    errors: Dict[str, str] = {}

    demo_mode = bool(user_input.get(CONF_DEMO_MODE))
    if not demo_mode:
        api_key = (user_input.get(CONF_API_KEY) or "").strip()
        if len(api_key) < 8:
            errors[CONF_API_KEY] = ERROR_INVALID_API_KEY

        url = (user_input.get(CONF_BASE_URL) or "").strip()
        split = urlsplit(url)
        if split.scheme not in ("http", "https") or not split.netloc:
            errors[CONF_BASE_URL] = ERROR_INVALID_URL

    base_tariff = user_input.get(CONF_BASE_TARIFF_RP)
    if base_tariff is not None and float(base_tariff) <= 0:
        errors[CONF_BASE_TARIFF_RP] = ERROR_INVALID_TARIFF

    medium = float(
        user_input.get(CONF_MEDIUM_DISCOUNT_PCT, DEFAULT_MEDIUM_DISCOUNT_PCT)
    )
    high = float(user_input.get(CONF_HIGH_DISCOUNT_PCT, DEFAULT_HIGH_DISCOUNT_PCT))
    if not (0 <= medium < high <= 100):
        errors["base"] = ERROR_INVALID_DISCOUNTS
    return errors


class BkwConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow for BKW Dynamic Tariffs."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial user step."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            cleaned = dict(user_input)
            if not cleaned.get(CONF_API_KEY):
                cleaned[CONF_API_KEY] = ""
            errors = _validate(cleaned)
            if not errors:
                region = cleaned[CONF_REGION]
                short_name = REGIONS[region].split(" (")[0]
                return self.async_create_entry(
                    title=f"BKW Sonne scheint ({short_name})", data=cleaned
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_region_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle reconfiguration of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: Dict[str, str] = {}
        if user_input is not None:
            cleaned = dict(user_input)
            if not cleaned.get(CONF_API_KEY):
                cleaned[CONF_API_KEY] = entry.data.get(CONF_API_KEY, "")
            errors = _validate(cleaned)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, **cleaned}
                )
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_region_schema(defaults=entry.data),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Dict[str, Any]) -> FlowResult:
        """Start a reauth flow after an authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Ask for a new API key."""
        errors: Dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api_key = (user_input.get(CONF_API_KEY) or "").strip()
            if len(api_key) < 8:
                errors[CONF_API_KEY] = ERROR_INVALID_API_KEY
            else:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_API_KEY: api_key}
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            description_placeholders={
                CONF_BASE_URL: entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
            },
            errors=errors,
        )
