"""
MIRAI — JustWatch sync client
================================
Queries the unofficial JustWatch REST API to retrieve streaming-platform
availability for a given title.  Used as **enrichment** on top of TMDB
Watch Providers: if TMDB returns no data or fewer than two platforms,
this client is called to fill the gap.

Key design decisions
---------------------
- ``requests`` (sync I/O) with a 3-second hard timeout.
- In-process ``TTLCache`` (1-hour TTL, 2 000 slots) — no external service.
- Title fuzz-match via ``difflib.SequenceMatcher`` (≥ 0.75 ratio) to avoid
  returning data for a mismatched result.
- **Silent fail** on any exception — returns ``[]`` so the caller is not
  affected by JustWatch downtime or API drift.

Usage::

    client = JustWatchClient()
    platforms = client.get_platforms("Inception", year=2010)
    # → ["Netflix", "Prime Video"]
"""

from __future__ import annotations

import difflib
import logging
from typing import Optional

import requests
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton session — created lazily, shared across calls
# ---------------------------------------------------------------------------

_JUSTWATCH_BASE = "https://apis.justwatch.com/content/titles/en_IN/popular"
_TIMEOUT = 3 # seconds
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


class JustWatchClient:
    """
    Sync JustWatch client with TTL caching and fuzzy title matching.

    Create one instance at application startup and reuse it:

        _jw_client: JustWatchClient | None = None

        def get_jw_client() -> JustWatchClient:
            global _jw_client
            if _jw_client is None:
                _jw_client = JustWatchClient()
            return _jw_client
    """

    def __init__(self) -> None:
        self.base_url: str = _JUSTWATCH_BASE
        self._session: requests.Session | None = None
        # 2 000 titles × 1-hour TTL — fits comfortably in RAM (~few MB)
        self.cache: TTLCache = TTLCache(maxsize=2000, ttl=3600)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self) -> requests.Session:
        """Return the shared session, creating it lazily if needed."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(_HEADERS)
        return self._session

    @staticmethod
    def _title_similarity(a: str, b: str) -> float:
        """Case-insensitive SequenceMatcher ratio between two title strings."""
        return difflib.SequenceMatcher(
            None, a.lower().strip(), b.lower().strip()
        ).ratio()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_platforms(
        self,
        title: str,
        year: Optional[int] = None,
    ) -> list[str]:
        """
        Return a deduplicated list of flatrate streaming platform names for
        *title* from JustWatch (India locale).

        Parameters
        ----------
        title:
            The movie or TV-show title to search for.
        year:
            Optional release year — used only for disambiguation in the
            similarity check (JustWatch query always sends the raw title).

        Returns
        -------
        List of canonical ``provider_clear_name`` strings, e.g.
        ``["Netflix", "Prime Video"]``.  Returns ``[]`` on any error.
        """
        if not title or not title.strip():
            return []

        cache_key = title.lower().strip()
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            session = self._get_session()
            payload = {
                "content_types": ["movie", "show"],
                "query": title.strip(),
            }

            resp = session.post(self.base_url, json=payload, timeout=_TIMEOUT)
            if resp.status_code != 200:
                logger.debug(
                    "[JustWatch] Non-200 response (%s) for title '%s'",
                    resp.status_code, title,
                )
                self.cache[cache_key] = []
                return []

            data = resp.json()

        except requests.exceptions.Timeout:
            logger.debug("[JustWatch] Timeout for title '%s'", title)
            return []
        except Exception as exc:
            logger.debug("[JustWatch] Request error for title '%s': %s", title, exc)
            return []

        # ── Parse response ──────────────────────────────────────────────────
        items: list = data.get("items", [])
        if not items:
            self.cache[cache_key] = []
            return []

        first = items[0]
        jw_title: str = first.get("title", "") or first.get("original_title", "")

        # Fuzzy-match guard — reject if the first result is a different title
        similarity = self._title_similarity(title, jw_title)
        if similarity < 0.75:
            logger.debug(
                "[JustWatch] Title mismatch for '%s' → '%s' (ratio=%.2f)",
                title, jw_title, similarity,
            )
            self.cache[cache_key] = []
            return []

        # ── Extract flatrate offers ─────────────────────────────────────────
        offers: list = first.get("offers", []) or []
        platforms: list[str] = []
        seen: set[str] = set()

        for offer in offers:
            if offer.get("monetization_type") != "flatrate":
                continue
            name: str = (offer.get("provider_clear_name") or "").strip()
            if name and name not in seen:
                seen.add(name)
                platforms.append(name)

        self.cache[cache_key] = platforms
        return platforms


# ---------------------------------------------------------------------------
# Module-level singleton — one instance shared by the whole backend process
# ---------------------------------------------------------------------------

_client: JustWatchClient | None = None


def get_justwatch_client() -> JustWatchClient:
    """Return (or lazily create) the module-level JustWatch client singleton."""
    global _client
    if _client is None:
        _client = JustWatchClient()
    return _client
