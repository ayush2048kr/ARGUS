"""
enrich_employee_context.py
==========================
ARGUS M1 — Monthly LDAP Context Enrichment

For each event in the master canonical dataset (argus_all_events), this
module attaches the contextual fields available in the monthly LDAP snapshot
that corresponds to the event's month.

Join sequence (per M1 spec §5):
    Raw activity user ID
        → normalize_raw_user_id()   [normalize_user_id.py]
        → monthly LDAP record       [data/raw/LDAP/YYYY-MM.csv]
        → ARGUS EMP### user_id      [data/processed/user_mapping.csv]

Only the ``role`` field is populated from LDAP (LDAP column ``Role``).
The ``Domain`` field is present in LDAP but absent from the canonical schema;
it is captured in the enrichment output under ``ldap_domain`` for downstream
coordination with M2 without altering the shared schema.

Fields that are absent from the raw data sources remain null:
    department, work_schedule, access_level, resource_sensitivity,
    location, source_ip

Employee names and email addresses are NEVER written to output files.

Enrichment match status codes (``context_match_status`` column):
    MATCHED             — user found in the monthly LDAP snapshot
    USER_NOT_IN_MONTH   — ARGUS user_id has no entry for this event's month
    INVALID_USER_ID     — the event carries a null/blank ARGUS user_id
    INVALID_TIMESTAMP   — the event timestamp is null/unparseable
    LDAP_MONTH_MISSING  — the LDAP file for this month is not available

A failed join is a data-quality condition, NOT a risk indicator.
All valid events are preserved regardless of enrichment success.

Outputs (written under data/processed/):
    context_enriched_events/        — Parquet partitioned by source
    user_month_context.csv          — one row per (argus_user_id, month)
    context_enrichment_validation.json — validation report (appended/merged)

Usage:
    python data/src/enrich_employee_context.py

Dependencies: pandas, pyarrow (already in .venv)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# ---------------------------------------------------------------------------
# Sibling-module import (works when run from repo root)
# ---------------------------------------------------------------------------
_SRC_DIR = os.path.join(os.path.dirname(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from normalize_user_id import normalize_series, normalize_raw_user_id  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MASTER_EVENTS_PATH = "data/processed/argus_all_events"
USER_MAPPING_CSV = "data/processed/user_mapping.csv"
LDAP_DIR = "data/raw/LDAP"

OUTPUT_ENRICHED_DIR = "data/processed/context_enriched_events"
OUTPUT_USER_MONTH_CTX = "data/processed/user_month_context.csv"
OUTPUT_VALIDATION_JSON = "data/processed/context_enrichment_validation.json"

# Fields populated from LDAP (only ``role`` is in the canonical schema)
LDAP_FIELDS_TO_ATTACH = ["role", "ldap_domain"]

# Canonical schema columns (must not be altered)
CANONICAL_COLUMNS = [
    "event_id", "user_id", "timestamp", "source", "event_type", "action",
    "resource", "resource_sensitivity", "source_ip", "destination",
    "device_id", "location", "role", "department", "work_schedule",
    "access_level", "is_external",
]

# Match status codes
STATUS_MATCHED = "MATCHED"
STATUS_NOT_IN_MONTH = "USER_NOT_IN_MONTH"
STATUS_INVALID_USER = "INVALID_USER_ID"
STATUS_INVALID_TS = "INVALID_TIMESTAMP"
STATUS_LDAP_MISSING = "LDAP_MONTH_MISSING"


# ---------------------------------------------------------------------------
# LDAP snapshot loader / cache
# ---------------------------------------------------------------------------

class LdapSnapshotCache:
    """
    Lazy-loads and caches monthly LDAP snapshots keyed by (year, month).
    Exposes a lookup by (argus_user_id, year, month) using the shared
    user_mapping to translate EMP### → bare LDAP user_id.
    """

    def __init__(self, ldap_dir: str, user_mapping_df: pd.DataFrame):
        self._dir = ldap_dir
        # Build: argus_user_id → bare_ldap_id
        self._emp_to_bare: dict[str, str] = {}
        for _, row in user_mapping_df.iterrows():
            try:
                bare = normalize_raw_user_id(str(row["raw_user_id"]))
                self._emp_to_bare[str(row["user_id"])] = bare
            except (ValueError, TypeError):
                pass  # malformed mapping row — skip silently

        self._cache: dict[tuple[int, int], pd.DataFrame | None] = {}
        self._available: set[tuple[int, int]] = set()
        self._missing: set[tuple[int, int]] = set()

    def _load(self, year: int, month: int) -> pd.DataFrame | None:
        key = (year, month)
        if key in self._cache:
            return self._cache[key]
        fname = f"{year:04d}-{month:02d}.csv"
        fpath = os.path.join(self._dir, fname)
        if not os.path.isfile(fpath):
            self._cache[key] = None
            self._missing.add(key)
            return None
        try:
            df = pd.read_csv(fpath, dtype=str, keep_default_na=False)
            # Build lookup: bare_user_id → {Role, Domain}
            if "user_id" not in df.columns:
                self._cache[key] = None
                self._missing.add(key)
                return None
            df = df[df["user_id"].str.strip() != ""].copy()
            df["_bare_id"] = df["user_id"].str.strip()
            df = df.drop_duplicates(subset=["_bare_id"], keep="first")
            df = df.set_index("_bare_id")
            self._cache[key] = df
            self._available.add(key)
            return df
        except Exception:
            self._cache[key] = None
            self._missing.add(key)
            return None

    def lookup(
        self,
        argus_user_id: str,
        year: int,
        month: int,
    ) -> tuple[str, str | None, str | None]:
        """
        Look up contextual fields for one (argus_user_id, year, month).

        Returns
        -------
        (status, role, ldap_domain)
            status is one of the STATUS_* constants.
            role and ldap_domain are None when not available.
        """
        if not argus_user_id or pd.isna(argus_user_id):
            return STATUS_INVALID_USER, None, None

        snapshot = self._load(year, month)
        if snapshot is None:
            return STATUS_LDAP_MISSING, None, None

        bare = self._emp_to_bare.get(argus_user_id)
        if bare is None:
            # EMP### not in mapping (should not happen in a consistent pipeline)
            return STATUS_INVALID_USER, None, None

        if bare not in snapshot.index:
            return STATUS_NOT_IN_MONTH, None, None

        row = snapshot.loc[bare]
        role = row.get("Role", None)
        domain = row.get("Domain", None)

        # Treat blank strings as null
        role = str(role).strip() if role and str(role).strip() else None
        domain = str(domain).strip() if domain and str(domain).strip() else None

        return STATUS_MATCHED, role, domain

    @property
    def available_months(self) -> set[tuple[int, int]]:
        return self._available

    @property
    def missing_months(self) -> set[tuple[int, int]]:
        return self._missing


# ---------------------------------------------------------------------------
# Main enrichment pipeline
# ---------------------------------------------------------------------------

def enrich_employee_context(
    master_path: str = MASTER_EVENTS_PATH,
    ldap_dir: str = LDAP_DIR,
    user_mapping_csv: str = USER_MAPPING_CSV,
    output_dir: str = OUTPUT_ENRICHED_DIR,
    output_user_month: str = OUTPUT_USER_MONTH_CTX,
    output_validation: str = OUTPUT_VALIDATION_JSON,
) -> dict:
    """
    Run the full LDAP context-enrichment pipeline.

    Reads the master canonical parquet dataset, attaches monthly LDAP context
    to each event, writes enriched outputs, and returns a validation report.
    """
    print("============================================================")
    print("ARGUS M1 — LDAP CONTEXT ENRICHMENT PIPELINE")
    print("============================================================")

    report: dict = {
        "pipeline": "enrich_employee_context",
        "input": {
            "master_events_path": master_path,
            "ldap_dir": ldap_dir,
            "user_mapping_csv": user_mapping_csv,
        },
        "output": {
            "enriched_events_dir": output_dir,
            "user_month_context_csv": output_user_month,
            "validation_json": output_validation,
        },
        "counts": {},
        "match_status_breakdown": {},
        "missing_ldap_months": [],
        "available_ldap_months": [],
        "monthly_coverage": {},
        "warnings": [],
        "validation_passed": False,
    }

    # ------------------------------------------------------------------
    # 1. Pre-flight checks
    # ------------------------------------------------------------------
    print("\n[1/7] Pre-flight checks...")

    if not os.path.isdir(master_path):
        msg = f"Master events not found: {master_path}"
        report["warnings"].append(msg)
        _write_validation(report, output_validation)
        print(f"  [FATAL] {msg}")
        return report

    if not os.path.isfile(user_mapping_csv):
        msg = f"User mapping CSV not found: {user_mapping_csv}"
        report["warnings"].append(msg)
        _write_validation(report, output_validation)
        print(f"  [FATAL] {msg}")
        return report

    if not os.path.isdir(ldap_dir):
        msg = (
            f"LDAP directory not found: {ldap_dir!r}. "
            "Create data/raw/LDAP/ and place the 18 monthly CSV files there, "
            "then re-run enrich_employee_context.py."
        )
        report["warnings"].append(msg)
        _write_validation(report, output_validation)
        print(f"  [FATAL] {msg}")
        return report

    print("  All required inputs present.")

    # ------------------------------------------------------------------
    # 2. Load user mapping
    # ------------------------------------------------------------------
    print("\n[2/7] Loading user mapping...")
    user_mapping_df = pd.read_csv(user_mapping_csv, dtype=str)
    print(f"  User mapping rows: {len(user_mapping_df):,d}")
    report["counts"]["user_mapping_rows"] = len(user_mapping_df)

    # ------------------------------------------------------------------
    # 3. Initialise LDAP cache
    # ------------------------------------------------------------------
    print("\n[3/7] Initialising LDAP snapshot cache...")
    cache = LdapSnapshotCache(ldap_dir, user_mapping_df)

    # Pre-warm all 18 expected months
    from validate_ldap_snapshots import EXPECTED_MONTHS
    for y, m in EXPECTED_MONTHS:
        cache._load(y, m)

    report["available_ldap_months"] = [
        f"{y:04d}-{m:02d}" for y, m in sorted(cache.available_months)
    ]
    report["missing_ldap_months"] = [
        f"{y:04d}-{m:02d}" for y, m in sorted(cache.missing_months)
    ]
    print(f"  LDAP months available : {len(cache.available_months)}/18")
    print(f"  LDAP months missing   : {len(cache.missing_months)}/18")
    if cache.missing_months:
        print("  Missing months:", report["missing_ldap_months"])
        report["warnings"].append(
            f"{len(cache.missing_months)} LDAP month(s) missing: "
            + ", ".join(report["missing_ldap_months"])
        )

    # ------------------------------------------------------------------
    # 4. Read master canonical events (parquet, partitioned)
    # ------------------------------------------------------------------
    print("\n[4/7] Reading master canonical events...")
    master_df = _read_parquet_dir(master_path)
    total_input = len(master_df)
    report["counts"]["input_events_total"] = total_input
    print(f"  Total input events: {total_input:,d}")

    # Per-source counts
    for src, grp in master_df.groupby("source"):
        report["counts"][f"input_{src}_events"] = len(grp)
        print(f"  {src:8s} events: {len(grp):,d}")

    # Invalid timestamp check
    null_ts_count = int(master_df["timestamp"].isna().sum())
    report["counts"]["invalid_timestamp_events"] = null_ts_count
    if null_ts_count > 0:
        print(f"  WARNING: {null_ts_count} events with null timestamp — "
              "will receive status INVALID_TIMESTAMP.")
        report["warnings"].append(
            f"{null_ts_count} events have null timestamps."
        )

    # ------------------------------------------------------------------
    # 5. Perform month-aligned LDAP context join
    # ------------------------------------------------------------------
    print("\n[5/7] Attaching monthly LDAP context...")

    def _enrich_row(row):
        ts = row["timestamp"]
        uid = row["user_id"]

        if pd.isna(ts):
            return STATUS_INVALID_TS, None, None

        try:
            dt = pd.Timestamp(ts)
            y, m = dt.year, dt.month
        except Exception:
            return STATUS_INVALID_TS, None, None

        return cache.lookup(uid, y, m)

    # Apply row-wise (event count is in the millions — use vectorised approach
    # by extracting year/month first then doing a group-lookup)
    master_df = master_df.copy()
    master_df["_year"] = pd.to_datetime(master_df["timestamp"], errors="coerce").dt.year
    master_df["_month"] = pd.to_datetime(master_df["timestamp"], errors="coerce").dt.month

    # Initialise output columns
    master_df["context_match_status"] = STATUS_INVALID_TS
    master_df["role"] = None        # overwrite canonical null with LDAP value
    master_df["ldap_domain"] = None  # extra field not in canonical schema

    # Vectorised per-month group processing
    valid_ts_mask = master_df["_year"].notna() & master_df["_month"].notna()
    invalid_ts_mask = ~valid_ts_mask
    master_df.loc[invalid_ts_mask, "context_match_status"] = STATUS_INVALID_TS

    null_uid_mask = master_df["user_id"].isna() | (master_df["user_id"] == "")
    master_df.loc[valid_ts_mask & null_uid_mask, "context_match_status"] = STATUS_INVALID_USER

    processable_mask = valid_ts_mask & ~null_uid_mask
    processable = master_df[processable_mask]

    print(f"  Events with valid timestamp & user_id: {int(processable_mask.sum()):,d}")

    # Group by (year, month) to minimise repeated snapshot loads
    status_list = [""] * len(master_df)
    role_list = [None] * len(master_df)
    domain_list = [None] * len(master_df)

    # Keep track of row indices
    master_df = master_df.reset_index(drop=True)

    # Set defaults for non-processable rows first
    for idx in master_df.index[invalid_ts_mask]:
        status_list[idx] = STATUS_INVALID_TS
    for idx in master_df.index[valid_ts_mask & null_uid_mask]:
        status_list[idx] = STATUS_INVALID_USER

    # Process the valid rows
    processable_idx = master_df.index[processable_mask]
    processable_df = master_df.loc[processable_idx, ["user_id", "_year", "_month"]]

    # Group by (year, month) to batch calls
    groups = processable_df.groupby(["_year", "_month"])
    group_count = len(groups)
    print(f"  Processing {group_count} (year, month) groups...")

    processed_events = 0
    monthly_coverage: dict[str, dict] = {}

    for (y, m), grp_idx in groups.groups.items():
        ym_key = f"{int(y):04d}-{int(m):02d}"
        grp = processable_df.loc[grp_idx]

        matched = not_in_month = ldap_miss = invalid_uid = 0

        for row_idx, row in grp.iterrows():
            status, role, domain = cache.lookup(str(row["user_id"]), int(y), int(m))
            status_list[row_idx] = status
            role_list[row_idx] = role
            domain_list[row_idx] = domain

            if status == STATUS_MATCHED:
                matched += 1
            elif status == STATUS_NOT_IN_MONTH:
                not_in_month += 1
            elif status == STATUS_LDAP_MISSING:
                ldap_miss += 1
            else:
                invalid_uid += 1

        total_grp = len(grp)
        monthly_coverage[ym_key] = {
            "events": total_grp,
            STATUS_MATCHED: matched,
            STATUS_NOT_IN_MONTH: not_in_month,
            STATUS_LDAP_MISSING: ldap_miss,
            STATUS_INVALID_USER: invalid_uid,
            "coverage_pct": round(matched / total_grp * 100, 2) if total_grp else 0,
        }
        processed_events += total_grp

    master_df["context_match_status"] = status_list
    master_df["role"] = role_list
    master_df["ldap_domain"] = domain_list

    # Final status for any remaining blanks (shouldn't occur)
    master_df.loc[master_df["context_match_status"] == "", "context_match_status"] = STATUS_INVALID_USER

    report["monthly_coverage"] = monthly_coverage

    # ------------------------------------------------------------------
    # 6. Compute summary stats
    # ------------------------------------------------------------------
    status_counts = master_df["context_match_status"].value_counts().to_dict()
    report["match_status_breakdown"] = status_counts
    total_output = len(master_df)
    report["counts"]["output_events_total"] = total_output

    print("\n  Enrichment match status breakdown:")
    for status, count in sorted(status_counts.items()):
        pct = count / total_output * 100 if total_output else 0
        print(f"    {status:25s}: {count:>10,d}  ({pct:5.2f}%)")

    events_lost = total_input - total_output
    report["counts"]["events_lost"] = events_lost
    report["counts"]["events_preserved"] = total_output
    if events_lost != 0:
        msg = f"EVENT COUNT MISMATCH: input={total_input}, output={total_output}, lost={events_lost}"
        report["warnings"].append(msg)
        print(f"\n  [WARNING] {msg}")
    else:
        print(f"\n  Event preservation: ALL {total_output:,d} events preserved (0 lost).")

    # Role fill stats
    matched_with_role = int(
        (master_df["context_match_status"] == STATUS_MATCHED)
        & master_df["role"].notna()
    ).sum() if STATUS_MATCHED in status_counts else 0
    matched_missing_role = (
        status_counts.get(STATUS_MATCHED, 0) - matched_with_role
    )
    report["counts"]["matched_events_with_role"] = matched_with_role
    report["counts"]["matched_events_missing_role"] = matched_missing_role

    # ------------------------------------------------------------------
    # 7. Write outputs
    # ------------------------------------------------------------------
    print("\n[6/7] Writing enriched outputs...")

    # 6a. Enriched events parquet (select enriched schema columns)
    enriched_cols = CANONICAL_COLUMNS + ["context_match_status", "ldap_domain"]
    # Ensure we have all canonical columns (some may have been missing from
    # master if it's an older run — fill with None)
    for col in enriched_cols:
        if col not in master_df.columns:
            master_df[col] = None

    enriched_df = master_df[enriched_cols]

    os.makedirs(output_dir, exist_ok=True)
    _write_parquet_by_source(enriched_df, output_dir)
    print(f"  Enriched events written to: {output_dir}")

    # 6b. User-month context summary (one row per argus_user_id × month)
    print("\n  Building user_month_context summary...")
    valid_matched = master_df[master_df["context_match_status"] == STATUS_MATCHED].copy()
    if len(valid_matched) > 0:
        valid_matched["ym"] = (
            valid_matched["_year"].astype(int).map(lambda x: f"{x:04d}")
            + "-"
            + valid_matched["_month"].astype(int).map(lambda x: f"{x:02d}")
        )
        user_month_ctx = (
            valid_matched.groupby(["user_id", "ym"])
            .agg(
                role=("role", "first"),
                ldap_domain=("ldap_domain", "first"),
                event_count=("event_id", "count"),
            )
            .reset_index()
            .rename(columns={"ym": "month"})
        )
    else:
        user_month_ctx = pd.DataFrame(
            columns=["user_id", "month", "role", "ldap_domain", "event_count"]
        )

    user_month_ctx.to_csv(output_user_month, index=False)
    print(f"  user_month_context.csv written: {len(user_month_ctx):,d} rows → {output_user_month}")
    report["counts"]["user_month_context_rows"] = len(user_month_ctx)

    # ------------------------------------------------------------------
    # 8. Write validation report
    # ------------------------------------------------------------------
    print("\n[7/7] Writing validation report...")
    report["validation_passed"] = (events_lost == 0)
    _write_validation(report, output_validation)

    print("\n============================================================")
    verdict = "PASSED" if report["validation_passed"] else "FAILED"
    print(f"LDAP CONTEXT ENRICHMENT — {verdict}")
    print("============================================================")

    return report


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def _read_parquet_dir(path: str) -> pd.DataFrame:
    """Read a directory of parquet part files into a single DataFrame."""
    part_files = sorted(
        [
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.endswith(".parquet")
        ]
    )
    if not part_files:
        raise FileNotFoundError(f"No .parquet files found in {path}")
    tables = [pq.read_table(f) for f in part_files]
    combined = pa.concat_tables(tables)
    return combined.to_pandas()


def _write_parquet_by_source(df: pd.DataFrame, output_dir: str) -> None:
    """Write enriched events, one parquet file per source."""
    for source, grp in df.groupby("source"):
        out_path = os.path.join(output_dir, f"{source.lower()}_enriched.parquet")
        table = pa.Table.from_pandas(grp, preserve_index=False)
        pq.write_table(table, out_path, compression="snappy")
        print(f"    {source}: {len(grp):,d} events → {out_path}")


def _write_validation(report: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"  Validation report written: {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = enrich_employee_context()
    sys.exit(0 if result["validation_passed"] else 1)
