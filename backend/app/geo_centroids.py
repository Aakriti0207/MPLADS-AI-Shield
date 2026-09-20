"""
State/district centroid fallback for project map coordinates.

Background
----------
`canonical_projects.csv` (the authoritative project universe -- see
app/routes/projects.py's module docstring) does not contain, and has
never contained, a latitude/longitude for any individual project --
confirmed by inspection of every column in that CSV (Map audit, Phase
1). The `projects` DB table's own `latitude`/`longitude` columns
(app/models.py) are likewise NULL for essentially every real row: that
model's own Phase 2 docstring explicitly lists them among the columns
"left NULL... rather than fabricated" when the source has no value.

There is therefore no accurate, project-level coordinate available
anywhere in this codebase's data sources. Geocoding a project down to
a building/site level would require an external address-geocoding
service and a real street address, neither of which exists here.

What this module provides instead
----------------------------------
An ADMINISTRATIVE-AREA CENTROID fallback, at two levels of precision:

  1. District centroid -- the approximate geographic center of the
     project's district, when the project's (state, district) can be
     matched (after normalization) against
     data/geo/district_centroids.csv.
  2. State centroid -- the mean of all matched district centroids
     within the project's state, used when the district itself can't
     be matched (spelling differences, or districts created after the
     reference file was generated -- see data/geo/SOURCE.md).

If even the state can't be resolved, `resolve_coordinates()` returns
(None, None, None) rather than guessing -- the same "leave it None,
don't fabricate it" convention this codebase already applies to every
other field with no real source value (see
app/routes/projects.py's `_clean_string`/`_decimal`/`_date` helpers).

These coordinates are NEVER a project's real location. They are the
same point for every project that shares a district (or state).
Callers and consumers MUST treat `location_precision` as part of the
contract: "district_centroid" and "state_centroid" are both
approximations, never a literal project address.

Data source
-----------
See data/geo/SOURCE.md for exactly where district_centroids.csv came
from, how it was generated, and its known coverage against this
project's canonical dataset.

Matching
--------
Project state/district strings (from canonical_projects.csv, or from
the `projects` DB table) are normalized -- uppercased, "&" expanded to
"AND", punctuation stripped, whitespace collapsed -- before lookup, so
formatting differences like "Banas Kantha" vs. "BANASKANTHA" don't
silently fail to match. This is a normalization-only EXACT match: it
deliberately never does fuzzy/approximate string matching, because a
wrong exact-sounding match (e.g. picking a similarly named district)
would itself be a fabricated project-specific coordinate -- exactly
what Phase 2's requirement #4 forbids. An unmatched district safely
falls back to its state centroid instead of guessing.
"""

from __future__ import annotations

import csv
import re
import threading
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DISTRICT_CENTROIDS_PATH = (
    BACKEND_ROOT / "data" / "geo" / "district_centroids.csv"
)

_QUANT = Decimal("0.000001")

_LOCK = threading.Lock()
_DISTRICT_CENTROIDS: (
    dict[tuple[str, str], tuple[Decimal, Decimal]] | None
) = None
_STATE_CENTROIDS: dict[str, tuple[Decimal, Decimal]] | None = None


def _normalize(value: Optional[str]) -> Optional[str]:
    """
    Normalize a state/district name for MATCHING ONLY (never for
    display -- the caller's original state/district strings are what
    the API still returns).
    """
    if value is None:
        return None
    text = str(value).upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _load() -> tuple[
    dict[tuple[str, str], tuple[Decimal, Decimal]],
    dict[str, tuple[Decimal, Decimal]],
]:
    """
    Load district_centroids.csv once per process and derive state
    centroids from it (the mean of that state's OWN matched district
    centroids -- not a separately sourced number, so it can never
    disagree with the district data it's built from).
    """
    global _DISTRICT_CENTROIDS, _STATE_CENTROIDS

    if _DISTRICT_CENTROIDS is not None and _STATE_CENTROIDS is not None:
        return _DISTRICT_CENTROIDS, _STATE_CENTROIDS

    with _LOCK:
        if _DISTRICT_CENTROIDS is not None and _STATE_CENTROIDS is not None:
            return _DISTRICT_CENTROIDS, _STATE_CENTROIDS

        district_centroids: dict[tuple[str, str], tuple[Decimal, Decimal]] = {}
        # state_n -> [lat_sum, lon_sum, count]
        state_sums: dict[str, list] = {}

        with DISTRICT_CENTROIDS_PATH.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                state_n = _normalize(row.get("state"))
                district_n = _normalize(row.get("district"))
                if not state_n or not district_n:
                    continue
                try:
                    lat = Decimal(row["latitude"])
                    lon = Decimal(row["longitude"])
                except Exception:
                    continue

                district_centroids[(state_n, district_n)] = (lat, lon)

                bucket = state_sums.setdefault(
                    state_n, [Decimal("0"), Decimal("0"), 0]
                )
                bucket[0] += lat
                bucket[1] += lon
                bucket[2] += 1

        state_centroids = {
            state_n: (
                _quantize(lat_sum / count),
                _quantize(lon_sum / count),
            )
            for state_n, (lat_sum, lon_sum, count) in state_sums.items()
            if count > 0
        }

        _DISTRICT_CENTROIDS = district_centroids
        _STATE_CENTROIDS = state_centroids
        return _DISTRICT_CENTROIDS, _STATE_CENTROIDS


def resolve_coordinates(
    state: Optional[str],
    district: Optional[str],
) -> tuple[Optional[Decimal], Optional[Decimal], Optional[str]]:
    """
    Resolve an approximate (latitude, longitude, location_precision)
    for a project's state/district.

    location_precision is one of:
      "district_centroid" -- matched the project's own district.
      "state_centroid"    -- district unmatched; fell back to the
                              project's state.
      None                -- neither could be resolved. No
                              coordinates are returned rather than
                              guessed.

    Never returns a project-SPECIFIC coordinate -- see module
    docstring. The same (state, district) always resolves to the same
    point, by design.
    """
    district_centroids, state_centroids = _load()

    state_n = _normalize(state)
    district_n = _normalize(district)

    if state_n and district_n:
        hit = district_centroids.get((state_n, district_n))
        if hit is not None:
            return hit[0], hit[1], "district_centroid"

    if state_n:
        hit = state_centroids.get(state_n)
        if hit is not None:
            return hit[0], hit[1], "state_centroid"

    return None, None, None