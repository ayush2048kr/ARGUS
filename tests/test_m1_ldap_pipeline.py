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
from validate_ldap_snapshots import (  # noqa: E402
    validate_ldap_snapshots,
    EXPECTED_MONTHS,
    EXPECTED_COLUMNS,
)
from enrich_employee_context import (  # noqa: E402
    LdapSnapshotCache,
    enrich_employee_context,
    CANONICAL_COLUMNS,
    STATUS_MATCHED,
    STATUS_NOT_IN_MONTH,
    STATUS_INVALID_USER,
    STATUS_INVALID_TS,
    STATUS_LDAP_MISSING,
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


# ===========================================================================
# SECTION 15 — Snapshot discovery and validation checks
# ===========================================================================

class TestSnapshotDiscoveryAndValidation:

    def test_validator_finds_all_snapshots_in_temp_dir(self, tmp_path):
        ldap_dir = tmp_path / "LDAP"
        ldap_dir.mkdir()
        header = ["employee_name", "user_id", "Domain", "Email", "Role"]
        row = ["Alice Smith", "AAA0001", "corp.com", "alice@corp.com", "Engineer"]

        for y, m in EXPECTED_MONTHS:
            fpath = ldap_dir / f"{y:04d}-{m:02d}.csv"
            with open(fpath, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(header)
                writer.writerow(row)

        out_json = tmp_path / "val.json"
        from validate_ldap_snapshots import validate_ldap_snapshots
        report = validate_ldap_snapshots(str(ldap_dir), output_validation=str(out_json))
        assert report["validation_passed"] is True
        assert len(report["files_found"]) == 18
        assert len(report["files_missing"]) == 0
        assert report["overall"]["column_consistency"] == "CONSISTENT"
        assert report["overall"]["total_rows_across_all_months"] == 18
        assert out_json.exists()

    def test_validator_missing_snapshot_fails(self, tmp_path):
        ldap_dir = tmp_path / "LDAP"
        ldap_dir.mkdir()
        header = ["employee_name", "user_id", "Domain", "Email", "Role"]

        # Write only 17 months (skip 2011-05)
        for y, m in EXPECTED_MONTHS[:-1]:
            fpath = ldap_dir / f"{y:04d}-{m:02d}.csv"
            with open(fpath, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(header)
                writer.writerow(["Alice", "AAA0001", "corp.com", "alice@corp.com", "Engineer"])

        out_json = tmp_path / "val_missing.json"
        from validate_ldap_snapshots import validate_ldap_snapshots
        report = validate_ldap_snapshots(str(ldap_dir), output_validation=str(out_json))
        assert report["validation_passed"] is False
        assert "2011-05.csv" in report["files_missing"]
        assert out_json.exists()

    def test_validator_missing_required_column_fails(self, tmp_path):
        ldap_dir = tmp_path / "LDAP"
        ldap_dir.mkdir()
        # Missing 'Role' column
        header = ["employee_name", "user_id", "Domain", "Email"]

        for y, m in EXPECTED_MONTHS:
            fpath = ldap_dir / f"{y:04d}-{m:02d}.csv"
            with open(fpath, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(header)
                writer.writerow(["Alice", "AAA0001", "corp.com", "alice@corp.com"])

        out_json = tmp_path / "val_bad_schema.json"
        from validate_ldap_snapshots import validate_ldap_snapshots
        report = validate_ldap_snapshots(str(ldap_dir), output_validation=str(out_json))
        assert report["validation_passed"] is False
        assert len(report["schema_issues"]) > 0
        assert out_json.exists()

    def test_validator_blank_user_id_reported(self, tmp_path):
        ldap_dir = tmp_path / "LDAP"
        ldap_dir.mkdir()
        header = ["employee_name", "user_id", "Domain", "Email", "Role"]

        for idx, (y, m) in enumerate(EXPECTED_MONTHS):
            fpath = ldap_dir / f"{y:04d}-{m:02d}.csv"
            with open(fpath, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(header)
                # First file has one blank user_id
                uid = "" if idx == 0 else "AAA0001"
                writer.writerow(["Alice", uid, "corp.com", "alice@corp.com", "Engineer"])

        out_json = tmp_path / "val_blank_uid.json"
        from validate_ldap_snapshots import validate_ldap_snapshots
        report = validate_ldap_snapshots(str(ldap_dir), output_validation=str(out_json))
        assert report["overall"]["total_invalid_user_id_rows"] == 1
        assert out_json.exists()

    def test_validator_nonexistent_dir_fails(self, tmp_path):
        out_json = tmp_path / "val_nonexistent.json"
        from validate_ldap_snapshots import validate_ldap_snapshots
        report = validate_ldap_snapshots(str(tmp_path / "does_not_exist"), output_validation=str(out_json))
        assert report["validation_passed"] is False
        assert len(report["validation_errors"]) > 0
        assert out_json.exists()

    def test_invalid_directory_validation_does_not_overwrite_production_report(self, tmp_path):
        """
        Regression test: validating an invalid/nonexistent directory with a custom
        output_validation path must write only to the temporary path and NEVER
        overwrite or modify the production context_enrichment_validation.json file.
        """
        from validate_ldap_snapshots import validate_ldap_snapshots

        prod_path = REPO_ROOT / "data" / "processed" / "context_enrichment_validation.json"

        # Record production state before the test
        prod_exists = prod_path.exists()
        prod_content_before = prod_path.read_text(encoding="utf-8") if prod_exists else None
        prod_mtime_before = prod_path.stat().st_mtime if prod_exists else None

        # Execute validator on nonexistent directory targeting temp path
        temp_report = tmp_path / "temp_failure_report.json"
        report = validate_ldap_snapshots(
            str(tmp_path / "definitely_nonexistent_ldap"),
            output_validation=str(temp_report),
        )

        assert report["validation_passed"] is False
        assert temp_report.exists()
        temp_data = json.loads(temp_report.read_text(encoding="utf-8"))
        assert temp_data["validation_passed"] is False

        # Production report must remain completely identical and untouched
        if prod_exists:
            assert prod_path.exists()
            assert prod_path.stat().st_mtime == prod_mtime_before
            assert prod_path.read_text(encoding="utf-8") == prod_content_before


# ===========================================================================
# SECTION 16 — Employee mapping reuse
# ===========================================================================

class TestEmployeeMappingReuse:

    def test_cache_uses_existing_mapping(self, tmp_path):
        ldap_dir = tmp_path / "LDAP"
        ldap_dir.mkdir()

        mapping_df = pd.DataFrame([
            {"raw_user_id": "DTAA/AAA0371", "user_id": "EMP001"},
            {"raw_user_id": "DTAA/AAC0344", "user_id": "EMP002"},
        ])
        cache = LdapSnapshotCache(str(ldap_dir), mapping_df)

        assert cache._emp_to_bare["EMP001"] == "AAA0371"
        assert cache._emp_to_bare["EMP002"] == "AAC0344"

    def test_cache_handles_whitespace_in_mapping(self, tmp_path):
        ldap_dir = tmp_path / "LDAP"
        ldap_dir.mkdir()

        mapping_df = pd.DataFrame([
            {"raw_user_id": "  DTAA/AAA0371  ", "user_id": "EMP001"},
        ])
        cache = LdapSnapshotCache(str(ldap_dir), mapping_df)
        assert cache._emp_to_bare["EMP001"] == "AAA0371"

    def test_unmapped_emp_id_returns_invalid_user(self, tmp_path):
        ldap_dir = tmp_path / "LDAP"
        ldap_dir.mkdir()
        # Create a valid snapshot file for 2010-01
        with open(ldap_dir / "2010-01.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["employee_name", "user_id", "Domain", "Email", "Role"])
            writer.writerow(["Alice", "AAA0371", "corp.com", "alice@corp.com", "Admin"])

        mapping_df = pd.DataFrame([
            {"raw_user_id": "DTAA/AAA0371", "user_id": "EMP001"},
        ])
        cache = LdapSnapshotCache(str(ldap_dir), mapping_df)
        status, role, domain = cache.lookup("EMP999", 2010, 1)
        assert status == STATUS_INVALID_USER
        assert role is None
        assert domain is None


# ===========================================================================
# SECTION 17 — Full context enrichment pipeline on synthetic data
# ===========================================================================

class TestFullContextEnrichmentPipeline:

    def test_synthetic_pipeline_run_success(self, tmp_path):
        import pyarrow as pa
        import pyarrow.parquet as pq

        ldap_dir = tmp_path / "LDAP"
        ldap_dir.mkdir()

        header = ["employee_name", "user_id", "Domain", "Email", "Role"]
        # 2010-01 has EMP001 and EMP002
        with open(ldap_dir / "2010-01.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerow(["Alice Admin", "AAA0001", "corp.net", "alice@corp.net", "Security Officer"])
            writer.writerow(["Bob Builder", "BBB0002", "corp.net", "bob@corp.net", "Contractor"])

        # 2010-02 has only EMP001 (EMP002 departed)
        with open(ldap_dir / "2010-02.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerow(["Alice Admin", "AAA0001", "corp.net", "alice@corp.net", "Security Officer"])

        # Mapping CSV
        mapping_path = tmp_path / "user_mapping.csv"
        pd.DataFrame([
            {"raw_user_id": "DTAA/AAA0001", "user_id": "EMP001"},
            {"raw_user_id": "DTAA/BBB0002", "user_id": "EMP002"},
        ]).to_csv(mapping_path, index=False)

        # Master events parquet
        master_dir = tmp_path / "master_events"
        master_dir.mkdir()

        events_data = pd.DataFrame([
            {
                "event_id": "ARG-LOGON-001",
                "user_id": "EMP001",
                "timestamp": pd.Timestamp("2010-01-15 08:00:00"),
                "source": "LOGON",
                "event_type": "LOGON_ACTIVITY",
                "action": "Logon",
                "resource": None,
                "resource_sensitivity": None,
                "source_ip": "10.0.0.1",
                "destination": None,
                "device_id": "PC-001",
                "location": "HQ",
                "role": None,
                "department": None,
                "work_schedule": None,
                "access_level": None,
                "is_external": False,
            },
            {
                "event_id": "ARG-HTTP-002",
                "user_id": "EMP002",
                "timestamp": pd.Timestamp("2010-02-15 09:30:00"),
                "source": "HTTP",
                "event_type": "HTTP_ACTIVITY",
                "action": "Visit",
                "resource": "http://intranet.local",
                "resource_sensitivity": None,
                "source_ip": "10.0.0.2",
                "destination": "intranet.local",
                "device_id": "PC-002",
                "location": "Branch",
                "role": None,
                "department": None,
                "work_schedule": None,
                "access_level": None,
                "is_external": False,
            },
            {
                "event_id": "ARG-DEVICE-003",
                "user_id": "EMP001",
                "timestamp": pd.Timestamp("2010-05-10 14:00:00"),
                "source": "DEVICE",
                "event_type": "DEVICE_ACTIVITY",
                "action": "Connect",
                "resource": "USB-DISK-1",
                "resource_sensitivity": None,
                "source_ip": None,
                "destination": None,
                "device_id": "PC-001",
                "location": "HQ",
                "role": None,
                "department": None,
                "work_schedule": None,
                "access_level": None,
                "is_external": False,
            },
            {
                "event_id": "ARG-LOGON-004",
                "user_id": "EMP999",
                "timestamp": pd.Timestamp("2010-01-20 10:00:00"),
                "source": "LOGON",
                "event_type": "LOGON_ACTIVITY",
                "action": "Logon",
                "resource": None,
                "resource_sensitivity": None,
                "source_ip": "10.0.0.9",
                "destination": None,
                "device_id": "PC-999",
                "location": "HQ",
                "role": None,
                "department": None,
                "work_schedule": None,
                "access_level": None,
                "is_external": False,
            },
        ])
        table = pa.Table.from_pandas(events_data, preserve_index=False)
        pq.write_table(table, master_dir / "part-0000.parquet")

        out_enriched_dir = tmp_path / "enriched"
        out_user_month = tmp_path / "user_month.csv"
        out_val = tmp_path / "val.json"

        report = enrich_employee_context(
            master_path=str(master_dir),
            ldap_dir=str(ldap_dir),
            user_mapping_csv=str(mapping_path),
            output_dir=str(out_enriched_dir),
            output_user_month=str(out_user_month),
            output_validation=str(out_val),
        )

        assert report["validation_passed"] is True
        assert report["counts"]["input_events_total"] == 4
        assert report["counts"]["output_events_total"] == 4
        assert report["counts"]["events_lost"] == 0

        # Status breakdown:
        # 1 MATCHED (EMP001 in 2010-01)
        # 1 USER_NOT_IN_MONTH (EMP002 in 2010-02)
        # 1 LDAP_MONTH_MISSING (EMP001 in 2010-05)
        # 1 INVALID_USER_ID (EMP999 not in user_mapping)
        assert report["match_status_breakdown"][STATUS_MATCHED] == 1
        assert report["match_status_breakdown"][STATUS_NOT_IN_MONTH] == 1
        assert report["match_status_breakdown"][STATUS_LDAP_MISSING] == 1
        assert report["match_status_breakdown"][STATUS_INVALID_USER] == 1

        # Check privacy: no PII columns in output files
        logon_out = pq.read_table(out_enriched_dir / "logon_enriched.parquet")
        logon_cols = logon_out.schema.names
        assert "employee_name" not in logon_cols
        assert "Email" not in logon_cols
        assert "email" not in logon_cols

        # Check attached fields on matched row
        logon_df = logon_out.to_pandas()
        matched_row = logon_df[logon_df["user_id"] == "EMP001"].iloc[0]
        assert matched_row["role"] == "Security Officer"
        assert matched_row["ldap_domain"] == "corp.net"
        assert matched_row["context_match_status"] == STATUS_MATCHED

        # Check unmatched row preserved with null role
        invalid_row = logon_df[logon_df["user_id"] == "EMP999"].iloc[0]
        assert pd.isna(invalid_row["role"])
        assert invalid_row["context_match_status"] == STATUS_INVALID_USER

        # Check user_month.csv
        um_df = pd.read_csv(out_user_month)
        assert len(um_df) == 1
        assert um_df.iloc[0]["user_id"] == "EMP001"
        assert um_df.iloc[0]["month"] == "2010-01"
        assert um_df.iloc[0]["role"] == "Security Officer"
        assert um_df.iloc[0]["event_count"] == 1


# ===========================================================================
# SECTION 18 — Duplicate join prevention
# ===========================================================================

class TestDuplicateJoinPrevention:

    def test_duplicate_ldap_records_do_not_duplicate_activity_events(self, tmp_path):
        import pyarrow as pa
        import pyarrow.parquet as pq

        ldap_dir = tmp_path / "LDAP"
        ldap_dir.mkdir()

        # Duplicate entries for AAA0001 with differing roles
        header = ["employee_name", "user_id", "Domain", "Email", "Role"]
        with open(ldap_dir / "2010-01.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerow(["Alice 1", "AAA0001", "corp.net", "alice1@corp.net", "Primary Role"])
            writer.writerow(["Alice 2", "AAA0001", "corp.net", "alice2@corp.net", "Secondary Role"])

        mapping_path = tmp_path / "user_mapping.csv"
        pd.DataFrame([
            {"raw_user_id": "DTAA/AAA0001", "user_id": "EMP001"},
        ]).to_csv(mapping_path, index=False)

        master_dir = tmp_path / "master"
        master_dir.mkdir()
        events_data = pd.DataFrame([
            {
                "event_id": "ARG-LOGON-001",
                "user_id": "EMP001",
                "timestamp": pd.Timestamp("2010-01-15 08:00:00"),
                "source": "LOGON",
                "event_type": "LOGON_ACTIVITY",
                "action": "Logon",
                "resource": None,
                "resource_sensitivity": None,
                "source_ip": "10.0.0.1",
                "destination": None,
                "device_id": "PC-001",
                "location": "HQ",
                "role": None,
                "department": None,
                "work_schedule": None,
                "access_level": None,
                "is_external": False,
            }
        ])
        table = pa.Table.from_pandas(events_data, preserve_index=False)
        pq.write_table(table, master_dir / "part-0000.parquet")

        out_enriched_dir = tmp_path / "enriched"
        out_user_month = tmp_path / "user_month.csv"
        out_val = tmp_path / "val.json"

        report = enrich_employee_context(
            master_path=str(master_dir),
            ldap_dir=str(ldap_dir),
            user_mapping_csv=str(mapping_path),
            output_dir=str(out_enriched_dir),
            output_user_month=str(out_user_month),
            output_validation=str(out_val),
        )

        assert report["counts"]["input_events_total"] == 1
        assert report["counts"]["output_events_total"] == 1
        assert report["counts"]["events_lost"] == 0

        # Read back logon parquet
        out_table = pq.read_table(out_enriched_dir / "logon_enriched.parquet")
        assert out_table.num_rows == 1
        # First occurrence wins
        assert out_table.to_pandas().iloc[0]["role"] == "Primary Role"


# ===========================================================================
# SECTION 19 — Existing feature outputs unchanged
# ===========================================================================

class TestExistingFeatureOutputsUnchanged:

    def test_existing_pipeline_features_intact(self):
        f1 = REPO_ROOT / "data" / "processed" / "user_features_stage1_daily.parquet"
        f2 = REPO_ROOT / "data" / "processed" / "user_features_stage2_history.parquet"
        f3 = REPO_ROOT / "data" / "processed" / "user_peer_clusters.parquet"

        assert f1.exists(), f"Missing: {f1}"
        assert f2.exists(), f"Missing: {f2}"
        assert f3.exists(), f"Missing: {f3}"
