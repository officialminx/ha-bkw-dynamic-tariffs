"""Exceptions for the BKW Dynamic Tariffs integration."""
from __future__ import annotations


class BkwTariffError(Exception):
    """Base exception for the BKW Dynamic Tariffs integration."""


class BkwApiError(BkwTariffError):
    """Raised when the BKW API cannot be reached or returns an error."""


class BkwAuthError(BkwTariffError):
    """Raised when the API key is rejected (HTTP 401/403)."""


class BkwParseError(BkwTariffError):
    """Raised when the API response cannot be parsed."""
