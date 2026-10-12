"""
normalize_user_id.py
====================
Deterministic user-ID normalization for ARGUS.

Raw CERT activity logs carry identifiers such as ``DTAA/AAA0371``.
Monthly LDAP snapshots carry bare identifiers such as ``AAA0371``.

This module provides one canonical normalization function that strips the
known ``DTAA/`` prefix, trims whitespace, and rejects empty or malformed
inputs.  It does NOT use fuzzy matching, row ordering, employee names, or
any other heuristic transformation.

The function is used by both the activity-event pipeline (combine_events.py)
and the LDAP context-enrichment pipeline (enrich_employee_context.py) to
guarantee a single, shared join key.

Normalization contract (all callers must use this function):
    Raw activity ID  →  normalize_raw_user_id()  →  LDAP lookup key
    e.g.  "DTAA/AAA0371"  →  "AAA0371"
          " DTAA/AAA0371 "→  "AAA0371"   (leading/trailing whitespace stripped)
          "AAA0371"       →  "AAA0371"   (no prefix — returned as-is)
          ""              →  raises ValueError
          None            →  raises ValueError
          "DTAA/"         →  raises ValueError  (empty suffix)
          "  "            →  raises ValueError  (blank after strip)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Known prefix
# ---------------------------------------------------------------------------
_KNOWN_PREFIX = "DTAA/"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_raw_user_id(raw_id: str | None) -> str:
    """
    Normalize a raw CERT activity user ID to its bare LDAP-compatible form.

    Parameters
    ----------
    raw_id:
        A raw user identifier from a CERT log line, e.g. ``"DTAA/AAA0371"``
        or already-bare ``"AAA0371"``.

    Returns
    -------
    str
        The normalized (bare) user ID, e.g. ``"AAA0371"``.

    Raises
    ------
    ValueError
        If *raw_id* is None, empty, blank after stripping, or yields an
        empty string after prefix removal.
    TypeError
        If *raw_id* is not a string or None.
    """
    if raw_id is None:
        raise ValueError("raw_id is None — cannot normalize.")

    if not isinstance(raw_id, str):
        raise TypeError(
            f"raw_id must be a str, got {type(raw_id).__name__!r}: {raw_id!r}"
        )

    stripped = raw_id.strip()

    if not stripped:
        raise ValueError(f"raw_id is blank after stripping: {raw_id!r}")

    # Remove the known prefix when present
    if stripped.startswith(_KNOWN_PREFIX):
        bare = stripped[len(_KNOWN_PREFIX):]
    else:
        bare = stripped

    if not bare:
        raise ValueError(
            f"raw_id yields an empty string after prefix removal: {raw_id!r}"
        )

    return bare


def is_valid_raw_user_id(raw_id: str | None) -> bool:
    """
    Return True if *raw_id* can be successfully normalized, False otherwise.

    Convenience wrapper around :func:`normalize_raw_user_id` for use in
    filter/map pipelines where exceptions are inconvenient.
    """
    try:
        normalize_raw_user_id(raw_id)
        return True
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Pandas/Dask helper — vectorised via apply
# ---------------------------------------------------------------------------

def normalize_series(series):
    """
    Apply :func:`normalize_raw_user_id` element-wise to a pandas or Dask Series.

    Invalid values are replaced with ``None`` (NaN in pandas); they are NOT
    silently dropped.  Callers should inspect the resulting nulls and count them
    as data-quality findings, not as a risk signal.

    Parameters
    ----------
    series : pandas.Series or dask.dataframe.Series
        A Series of raw user ID strings.

    Returns
    -------
    pandas.Series or dask.dataframe.Series
        A same-length Series of normalized IDs.  Invalid inputs map to None.
    """
    def _safe_normalize(v):
        try:
            return normalize_raw_user_id(v)
        except (ValueError, TypeError):
            return None

    return series.apply(_safe_normalize)
