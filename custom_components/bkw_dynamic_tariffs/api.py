"""API client for the BKW dynamic tariffs («Sonne scheint») EMS interface."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import aiohttp

from .const import DEFAULT_MEDIUM_DISCOUNT_PCT, DEFAULT_HIGH_DISCOUNT_PCT, SUBSCRIPTION_HEADER, USER_AGENT
from .exceptions import BkwApiError, BkwAuthError, BkwParseError
from .models import BkwTariffData, build_demo_data, parse_windows_payload

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30  # seconds


class BkwApiClient:
    """Client for the BKW «Sonne scheint» discount window API.

    The client sends the user's subscription key as
    ``Ocp-Apim-Subscription-Key`` header (Azure API management style) and
    parses the response defensively (see :func:`parse_windows_payload`).
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        base_url: str,
        region: str,
        medium_pct: float = DEFAULT_MEDIUM_DISCOUNT_PCT,
        high_pct: float = DEFAULT_HIGH_DISCOUNT_PCT,
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._region = region
        self._medium_pct = medium_pct
        self._high_pct = high_pct

    def _build_url(self) -> str:
        split = urlsplit(self._base_url)
        query = split.query
        extra = urlencode({"region": self._region})
        if "region=" in query:
            query = query  # explicit region in URL wins
        else:
            query = f"{query}&{extra}" if query else extra
        return urlunsplit((split.scheme, split.netloc, split.path, query, split.fragment))

    async def async_get_data(self) -> BkwTariffData:
        """Fetch and parse the current discount window announcements."""
        url = self._build_url()
        headers = {
            "Accept": "application/json",
            SUBSCRIPTION_HEADER: self._api_key,
            "User-Agent": USER_AGENT,
        }
        _LOGGER.debug("Requesting BKW discount windows: %s", url)
        try:
            async with self._session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                if response.status in (401, 403):
                    raise BkwAuthError(
                        f"API key rejected by BKW API (HTTP {response.status})"
                    )
                if response.status == 429:
                    raise BkwApiError("BKW API rate limit exceeded (HTTP 429)")
                if response.status >= 500:
                    raise BkwApiError(
                        f"BKW API server error (HTTP {response.status})"
                    )
                if response.status >= 400:
                    raise BkwApiError(
                        f"BKW API client error (HTTP {response.status})"
                    )
                try:
                    payload: Any = await response.json(content_type=None)
                except ValueError as err:
                    text = await response.text()
                    raise BkwParseError(
                        f"BKW API returned non-JSON response: {text[:200]!r}"
                    ) from err
        except (TimeoutError, asyncio.TimeoutError) as err:
            raise BkwApiError("Timeout while contacting the BKW API") from err
        except aiohttp.ClientError as err:
            raise BkwApiError(f"Cannot connect to BKW API: {err}") from err

        try:
            return parse_windows_payload(
                payload, self._region, self._medium_pct, self._high_pct
            )
        except ValueError as err:
            raise BkwParseError(f"Unexpected BKW API payload: {err}") from err


class BkwDemoClient:
    """Demo client returning deterministic data without network access."""

    def __init__(
        self,
        region: str,
        medium_pct: float = DEFAULT_MEDIUM_DISCOUNT_PCT,
        high_pct: float = DEFAULT_HIGH_DISCOUNT_PCT,
    ) -> None:
        self._region = region
        self._medium_pct = medium_pct
        self._high_pct = high_pct

    async def async_get_data(self) -> BkwTariffData:
        return build_demo_data(self._region, self._medium_pct, self._high_pct)
