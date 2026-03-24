"""
MIRAI — Platform name normalizer
=================================
Centralises provider-name aliases so TMDB and JustWatch use identical
canonical names throughout the codebase.

Usage::

    from platform_normalizer import normalize
    name = normalize("Amazon Prime Video")  # → "Prime Video"
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Alias table — add new mappings here as needed
# ---------------------------------------------------------------------------
ALIASES: dict[str, str] = {
    # Amazon
    "Amazon Prime Video": "Prime Video",
    "Amazon Video":       "Prime Video",
    # Disney
    "Disney Plus":        "Disney+",
    "Disney Plus Hotstar":"Disney+ Hotstar",
    "Hotstar":            "Disney+ Hotstar",
    # Apple
    "Apple iTunes":       "Apple TV+",
    "Apple TV":           "Apple TV+",
    # Jio
    "Jio Cinema":         "JioCinema",
    "JioCinema Free":     "JioCinema",
    # Sun
    "Sun Nxt":            "SunNXT",
    "Sun NXT":            "SunNXT",
}


def normalize(name: str) -> str:
    """Return the canonical platform name for *name*, or *name* unchanged."""
    return ALIASES.get(name, name)


def normalize_list(names: list[str]) -> list[str]:
    """Normalize and deduplicate a list of platform names, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for n in names:
        canonical = normalize(n)
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result
