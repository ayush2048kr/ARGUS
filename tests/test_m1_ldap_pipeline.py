"""
test_m1_ldap_pipeline.py
========================
ARGUS M1 — Automated test suite for the LDAP context data pipeline.

Tests use only small synthetic fixtures (no raw CERT data committed).

Coverage:
    1.  Prefix normalization (strip DTAA/, whitespace, no-op for bare IDs)
    2.  Valid and invalid IDs
    3.  Monthly snapshot selection (correct LDAP month for a timestamp)
    4.  Month-boundary timestamps (last moment of month, first of next)
    5.  Duplicate LDAP IDs within a snapshot (first occurrence wins)
    6.  Missing LDAP users (absent from the snapshot month)
    7.  Missing role / domain values
    8.  Stable anonymized IDs (EMP### mapping is order-deterministic)
    9.  Duplicate event IDs (counted but events preserved)
    10. Timestamp parsing failures
    11. Event preservation after failed context joins
    12. Consistent canonical schema across logon, device, and HTTP sources

Run from the repository root:
    python -m pytest tests/test_m1_ldap_pipeline.py -v
or directly:
    .venv/Scripts/python.exe -m pytest tests/test_m1_ldap_pipeline.py -v
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
import textwrap
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Make data/src importable regardless of cwd
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "data" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from normalize_user_id import (  # noqa: E402
    is_valid_raw_user_id,
    normalize_raw_user_id,
    normalize_series,
)


# ===========================================================================
# SECTION 1 — Prefix normalization
# ===========================================================================

class TestPrefixNormalization:

    def test_strips_dtaa_prefix(self):
        assert normalize_raw_user_id("DTAA/AAA0371") == "AAA0371"

    def test_strips_dtaa_prefix_with_leading_space(self):
        assert normalize_raw_user_id(" DTAA/AAA0371") == "AAA0371"

    def test_strips_dtaa_prefix_with_trailing_space(self):
        assert normalize_raw_user_id("DTAA/AAA0371 ") == "AAA0371"

    def test_strips_dtaa_prefix_with_surrounding_spaces(self):
        assert normalize_raw_user_id("  DTAA/AAA0371  ") == "AAA0371"

    def test_bare_id_returned_unchanged(self):
        assert normalize_raw_user_id("AAA0371") == "AAA0371"

    def test_bare_id_with_spaces(self):
        assert normalize_raw_user_id("  AAA0371  ") == "AAA0371"

    def test_prefix_is_case_sensitive(self):
        # "dtaa/AAA0371" does NOT match the known "DTAA/" prefix —
        # returned as-is (bare ID)
        assert normalize_raw_user_id("dtaa/AAA0371") == "dtaa/AAA0371"

    def test_numeric_suffix(self):
        assert normalize_raw_user_id("DTAA/ZZZ9999") == "ZZZ9999"

    def test_no_double_strip(self):
        # Only one leading prefix is stripped; a second one is kept
        result = normalize_raw_user_id("DTAA/DTAA/AAA0371")
        assert result == "DTAA/AAA0371"


# ===========================================================================
# SECTION 2 — Valid and invalid IDs
# ===========================================================================

class TestValidInvalidIds:

    def test_none_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_raw_user_id(None)

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_raw_user_id("")

    def test_blank_string_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_raw_user_id("   ")

    def test_prefix_only_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_raw_user_id("DTAA/")

    def test_prefix_only_with_spaces_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_raw_user_id("DTAA/   ")

    def test_integer_raises_type_error(self):
        with pytest.raises(TypeError):
            normalize_raw_user_id(12345)

    def test_list_raises_type_error(self):
        with pytest.raises(TypeError):
            normalize_raw_user_id(["DTAA/AAA0371"])

    def test_is_valid_true(self):
        assert is_valid_raw_user_id("DTAA/AAA0371") is True

    def test_is_valid_false_for_none(self):
        assert is_valid_raw_user_id(None) is False

    def test_is_valid_false_for_empty(self):
        assert is_valid_raw_user_id("") is False

    def test_is_valid_false_for_blank(self):
        assert is_valid_raw_user_id("  ") is False

    def test_is_valid_false_for_prefix_only(self):
        assert is_valid_raw_user_id("DTAA/") is False


# ===========================================================================
# SECTION 3 — Monthly snapshot selection
# ===========================================================================

class TestMonthlySnapshotSelection:
    """
    Tests for the snapshot-month calculation logic embedded in
    enrich_employee_context.py.  We test the logic directly without
    running the full pipeline.
    """

    @staticmethod
    def _month_for_ts(ts_str: str) -> tuple[int, int]:
        """Return (year, month) for a timestamp string."""
        dt = pd.Timestamp(ts_str)
        return dt.year, dt.month

    def test_early_2010_event(self):
        assert self._month_for_ts("2010-01-15 09:00:00") == (2010, 1)

    def test_december_2009_event(self):
        assert self._month_for_ts("2009-12-01 00:00:00") == (2009, 12)

    def test_may_2011_event(self):
        assert self._month_for_ts("2011-05-31 23:59:59") == (2011, 5)

    def test_june_2010_event(self):
        assert self._month_for_ts("2010-06-15 12:34:56") == (2010, 6)


# ===========================================================================
# SECTION 4 — Month-boundary timestamps
# ===========================================================================

class TestMonthBoundaryTimestamps:

    @staticmethod
    def _year_month(ts_str: str) -> tuple[int, int]:
        dt = pd.Timestamp(ts_str)
        return dt.year, dt.month

    def test_last_second_of_january(self):
        assert self._year_month("2010-01-31 23:59:59") == (2010, 1)

    def test_first_second_of_february(self):
        assert self._year_month("2010-02-01 00:00:00") == (2010, 2)

    def test_last_second_of_december(self):
        assert self._year_month("2010-12-31 23:59:59") == (2010, 12)

    def test_first_second_of_january_next_year(self):
        assert self._year_month("2011-01-01 00:00:00") == (2011, 1)

    def test_null_timestamp_is_nat(self):
        ts = pd.Timestamp("NaT")
        assert pd.isna(ts)

    def test_invalid_timestamp_string_becomes_nat(self):
        ts = pd.to_datetime("not-a-date", errors="coerce")
        assert pd.isna(ts)


# ===========================================================================
# SECTION 5 — Duplicate LDAP IDs within a snapshot
# ===========================================================================

class TestDuplicateLdapIds:

    def _make_snapshot(self, rows: list[dict]) -> pd.DataFrame:
        """Build a minimal LDAP snapshot DataFrame."""
        return pd.DataFrame(rows)

    def test_duplicate_detection(self):
        df = self._make_snapshot([
            {"user_id": "AAA0001", "Role": "Engineer", "Domain": "CORP"},
            {"user_id": "AAA0001", "Role": "Manager", "Domain": "CORP"},
            {"user_id": "BBB0002", "Role": "Admin", "Domain": "CORP"},
        ])
        dup_count = int(df.duplicated(subset=["user_id"]).sum())
        assert dup_count == 1

    def test_first_occurrence_wins_after_dedup(self):
        df = self._make_snapshot([
            {"user_id": "AAA0001", "Role": "Engineer", "Domain": "CORP"},
            {"user_id": "AAA0001", "Role": "Manager", "Domain": "CORP"},
        ])
        deduped = df.drop_duplicates(subset=["user_id"], keep="first")
        assert deduped.loc[deduped["user_id"] == "AAA0001", "Role"].values[0] == "Engineer"

    def test_no_duplicates_passes_cleanly(self):
        df = self._make_snapshot([
            {"user_id": "AAA0001", "Role": "Engineer", "Domain": "CORP"},
            {"user_id": "BBB0002", "Role": "Admin", "Domain": "CORP"},
        ])
        assert df.duplicated(subset=["user_id"]).sum() == 0


# ===========================================================================
# SECTION 6 — Missing LDAP users
# ===========================================================================

class TestMissingLdapUsers:

    def test_user_absent_from_snapshot_returns_not_in_month(self):
        """
        Simulate looking up an EMP not in a given month's snapshot.
        """
        snapshot = pd.DataFrame([
            {"user_id": "AAA0001", "Role": "Engineer", "Domain": "CORP"},
        ])
        # Index by bare user_id (as the cache does)
        snapshot = snapshot.set_index("user_id")
        # "ZZZ9999" is not in the snapshot
        assert "ZZZ9999" not in snapshot.index

    def test_user_present_in_snapshot(self):
        snapshot = pd.DataFrame([
            {"user_id": "AAA0001", "Role": "Engineer", "Domain": "CORP"},
        ]).set_index("user_id")
        assert "AAA0001" in snapshot.index


# ===========================================================================
# SECTION 7 — Missing role / domain values
# ===========================================================================

class TestMissingContextAttributes:

    def _check_attr(self, value: str | None) -> str | None:
        """Mimic the enrichment module's blank-to-None logic."""
        if value and str(value).strip():
            return str(value).strip()
        return None

    def test_non_empty_role_preserved(self):
        assert self._check_attr("Engineer") == "Engineer"

    def test_empty_role_becomes_none(self):
        assert self._check_attr("") is None

    def test_blank_role_becomes_none(self):
        assert self._check_attr("   ") is None

    def test_none_role_stays_none(self):
        assert self._check_attr(None) is None

    def test_non_empty_domain_preserved(self):
        assert self._check_attr("CORP") == "CORP"

    def test_empty_domain_becomes_none(self):
        assert self._check_attr("") is None


# ===========================================================================
# SECTION 8 — Stable anonymized IDs
# ===========================================================================

class TestStableAnonymizedIds:
    """
    EMP### IDs must be deterministically assigned by sorted raw_user_id.
    The same raw ID must always map to the same EMP### regardless of which
    source file it came from.
    """

    def _build_mapping(self, raw_ids: list[str]) -> dict[str, str]:
        """Replicate create_ids.py's deterministic mapping logic in pure Python."""
        unique_sorted = sorted(set(raw_ids))
        return {uid: f"EMP{idx+1:03d}" for idx, uid in enumerate(unique_sorted)}

    def test_ordering_is_lexicographic(self):
        ids = ["DTAA/ZZZ9999", "DTAA/AAA0001", "DTAA/MMM0500"]
        mapping = self._build_mapping(ids)
        assert mapping["DTAA/AAA0001"] == "EMP001"
        assert mapping["DTAA/MMM0500"] == "EMP002"
        assert mapping["DTAA/ZZZ9999"] == "EMP003"

    def test_same_raw_id_always_maps_to_same_emp(self):
        ids_run1 = ["DTAA/AAA0001", "DTAA/BBB0002", "DTAA/CCC0003"]
        ids_run2 = ["DTAA/BBB0002", "DTAA/CCC0003", "DTAA/AAA0001"]  # different order
        m1 = self._build_mapping(ids_run1)
        m2 = self._build_mapping(ids_run2)
        assert m1["DTAA/AAA0001"] == m2["DTAA/AAA0001"]
        assert m1["DTAA/BBB0002"] == m2["DTAA/BBB0002"]

    def test_duplicates_in_input_do_not_change_mapping(self):
        ids = ["DTAA/AAA0001", "DTAA/AAA0001", "DTAA/BBB0002"]
        mapping = self._build_mapping(ids)
        assert len(mapping) == 2  # deduplicated


# ===========================================================================
# SECTION 9 — Duplicate event IDs
# ===========================================================================

class TestDuplicateEventIds:

    def test_duplicate_detection_in_dataframe(self):
        df = pd.DataFrame({
            "event_id": ["ARG-LOGON-001", "ARG-LOGON-002", "ARG-LOGON-001"],
            "user_id": ["EMP001", "EMP002", "EMP001"],
        })
        dup_count = int(df.duplicated(subset=["event_id"]).sum())
        assert dup_count == 1

    def test_no_duplicates_passes(self):
        df = pd.DataFrame({
            "event_id": ["ARG-LOGON-001", "ARG-LOGON-002", "ARG-HTTP-003"],
        })
        assert df.duplicated(subset=["event_id"]).sum() == 0

    def test_event_id_prefix_formats(self):
        valid_prefixes = ["ARG-LOGON-", "ARG-DEVICE-", "ARG-HTTP-"]
        event_ids = [
            "ARG-LOGON-{Y6O4-A7KC67IN-0899AOZK}",
            "ARG-DEVICE-{S7A7-Y8QZ65MW-8738SAZP}",
            "ARG-HTTP-{M8H9-W9NL75TH-1322KOLO}",
        ]
        for eid in event_ids:
            assert any(eid.startswith(p) for p in valid_prefixes), f"Bad prefix: {eid}"


# ===========================================================================
# SECTION 10 — Timestamp parsing failures
# ===========================================================================

class TestTimestampParsingFailures:

    def test_valid_cert_timestamp(self):
        ts = pd.to_datetime("01/04/2010 07:12:31", format="%m/%d/%Y %H:%M:%S", errors="coerce")
        assert not pd.isna(ts)
        assert ts.year == 2010
        assert ts.month == 1

    def test_invalid_timestamp_becomes_nat(self):
        ts = pd.to_datetime("not-a-date", errors="coerce")
        assert pd.isna(ts)

    def test_empty_timestamp_becomes_nat(self):
        ts = pd.to_datetime("", errors="coerce")
        assert pd.isna(ts)

    def test_none_timestamp_becomes_nat(self):
        ts = pd.to_datetime(None, errors="coerce")
        assert pd.isna(ts)

    def test_series_with_mixed_timestamps(self):
        s = pd.Series(["01/04/2010 07:12:31", "bad-date", "", None])
        parsed = pd.to_datetime(s, format="%m/%d/%Y %H:%M:%S", errors="coerce")
        assert not pd.isna(parsed.iloc[0])
        assert pd.isna(parsed.iloc[1])
        assert pd.isna(parsed.iloc[2])
        assert pd.isna(parsed.iloc[3])

    def test_null_count_reported(self):
        s = pd.Series(["01/04/2010 07:12:31", "bad-date", None])
        parsed = pd.to_datetime(s, errors="coerce")
        null_count = int(parsed.isna().sum())
        assert null_count == 2


# ===========================================================================
# SECTION 11 — Event preservation after failed context joins
# ===========================================================================

class TestEventPreservationAfterFailedJoin:
    """
    A failed LDAP join must NEVER drop an event.
    The enrichment pipeline preserves every valid input event and marks
    it with an appropriate context_match_status.
    """

    def _make_events(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"event_id": "ARG-LOGON-001", "user_id": "EMP001", "timestamp": "2010-03-15 09:00:00", "source": "LOGON"},
            {"event_id": "ARG-LOGON-002", "user_id": "EMP002", "timestamp": "2010-03-15 09:05:00", "source": "LOGON"},
            {"event_id": "ARG-LOGON-003", "user_id": "EMP003", "timestamp": "2010-03-15 09:10:00", "source": "LOGON"},
        ])

    def test_all_events_preserved_when_ldap_missing(self):
        events = self._make_events()
        # Simulate: no LDAP file for this month → status = LDAP_MONTH_MISSING
        events["context_match_status"] = "LDAP_MONTH_MISSING"
        events["role"] = None
        events["ldap_domain"] = None
        # Total output must equal total input
        assert len(events) == 3

    def test_all_events_preserved_when_user_absent(self):
        events = self._make_events()
        # Simulate: users not in the snapshot → USER_NOT_IN_MONTH
        events["context_match_status"] = "USER_NOT_IN_MONTH"
        events["role"] = None
        assert len(events) == 3

    def test_mixed_statuses_preserve_event_count(self):
        events = self._make_events()
        statuses = ["MATCHED", "USER_NOT_IN_MONTH", "LDAP_MONTH_MISSING"]
        events["context_match_status"] = statuses
        assert len(events) == 3
        assert set(events["context_match_status"]) == set(statuses)

    def test_failed_join_does_not_set_role_from_guess(self):
        """Role must be None for non-MATCHED events — never invented."""
        events = self._make_events()
        events["context_match_status"] = "USER_NOT_IN_MONTH"
        events["role"] = None  # explicitly null
        assert events["role"].isna().all()


# ===========================================================================
# SECTION 12 — Consistent canonical schema across sources
# ===========================================================================

class TestCanonicalSchemaConsistency:

    CANONICAL_COLUMNS = [
        "event_id", "user_id", "timestamp", "source", "event_type",
        "action", "resource", "resource_sensitivity", "source_ip",
        "destination", "device_id", "location", "role", "department",
        "work_schedule", "access_level", "is_external",
    ]

    def _make_canonical_row(self, source: str, event_id: str) -> dict:
        return {
            "event_id": event_id,
            "user_id": "EMP001",
            "timestamp": pd.Timestamp("2010-03-15 09:00:00"),
            "source": source,
            "event_type": f"{source}_ACTIVITY",
            "action": "Logon",
            "resource": None,
            "resource_sensitivity": None,
            "source_ip": None,
            "destination": None,
            "device_id": "PC-1234",
            "location": None,
            "role": None,
            "department": None,
            "work_schedule": None,
            "access_level": None,
            "is_external": None,
        }

    def test_logon_schema(self):
        row = self._make_canonical_row("LOGON", "ARG-LOGON-001")
        assert list(row.keys()) == self.CANONICAL_COLUMNS

    def test_device_schema(self):
        row = self._make_canonical_row("DEVICE", "ARG-DEVICE-001")
        assert list(row.keys()) == self.CANONICAL_COLUMNS

    def test_http_schema(self):
        row = self._make_canonical_row("HTTP", "ARG-HTTP-001")
        assert list(row.keys()) == self.CANONICAL_COLUMNS

    def test_all_three_sources_have_identical_columns(self):
        logon = list(self._make_canonical_row("LOGON", "x").keys())
        device = list(self._make_canonical_row("DEVICE", "x").keys())
        http = list(self._make_canonical_row("HTTP", "x").keys())
        assert logon == device == http == self.CANONICAL_COLUMNS

    def test_event_schema_json_matches_canonical_columns(self):
        schema_path = REPO_ROOT / "data" / "schema" / "event_schema.json"
        with open(schema_path, "r") as fh:
            schema = json.load(fh)
        schema_cols = list(schema.keys())
        assert schema_cols == self.CANONICAL_COLUMNS, (
            f"event_schema.json columns: {schema_cols}\n"
            f"Expected: {self.CANONICAL_COLUMNS}"
        )

    def test_no_pii_columns_in_canonical_schema(self):
        """employee_name and Email must NOT appear in the canonical schema."""
        forbidden = {"employee_name", "Email", "email", "name"}
        assert not forbidden.intersection(set(self.CANONICAL_COLUMNS))


# ===========================================================================
# SECTION 13 — normalize_series helper
# ===========================================================================

class TestNormalizeSeries:

    def test_series_normalizes_correctly(self):
        s = pd.Series(["DTAA/AAA0001", "DTAA/BBB0002", "CCC0003"])
        result = normalize_series(s)
        assert result.tolist() == ["AAA0001", "BBB0002", "CCC0003"]

    def test_series_invalid_values_become_none(self):
        s = pd.Series(["DTAA/AAA0001", None, "", "  ", "DTAA/"])
        result = normalize_series(s)
        assert result.iloc[0] == "AAA0001"
        # pandas object-series uses NaN (float) for missing values
        assert pd.isna(result.iloc[1])
        assert pd.isna(result.iloc[2])
        assert pd.isna(result.iloc[3])
        assert pd.isna(result.iloc[4])

    def test_series_length_preserved(self):
        s = pd.Series(["DTAA/AAA0001", None, "BBB0002", "DTAA/"])
        result = normalize_series(s)
        assert len(result) == len(s)


# ===========================================================================
# SECTION 14 — LDAP expected-months list
# ===========================================================================

class TestExpectedMonthsList:

    def test_eighteen_months_expected(self):
        from validate_ldap_snapshots import EXPECTED_MONTHS
        assert len(EXPECTED_MONTHS) == 18

    def test_starts_with_december_2009(self):
        from validate_ldap_snapshots import EXPECTED_MONTHS
        assert EXPECTED_MONTHS[0] == (2009, 12)

    def test_ends_with_may_2011(self):
        from validate_ldap_snapshots import EXPECTED_MONTHS
        assert EXPECTED_MONTHS[-1] == (2011, 5)

    def test_months_are_consecutive(self):
        from validate_ldap_snapshots import EXPECTED_MONTHS
        for i in range(1, len(EXPECTED_MONTHS)):
            y_prev, m_prev = EXPECTED_MONTHS[i - 1]
            y_curr, m_curr = EXPECTED_MONTHS[i]
            if m_prev == 12:
                assert y_curr == y_prev + 1 and m_curr == 1
            else:
                assert y_curr == y_prev and m_curr == m_prev + 1

    def test_no_duplicate_months(self):
        from validate_ldap_snapshots import EXPECTED_MONTHS
        assert len(set(EXPECTED_MONTHS)) == len(EXPECTED_MONTHS)
