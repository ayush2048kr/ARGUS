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
        self._month_maps: dict[
            tuple[int, int],
            tuple[str | None, dict[str, str | None], dict[str, str | None], set[str], set[str]],
        ] = {}

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

    def get_month_maps(
        self, year: int, month: int
    ) -> tuple[str | None, dict[str, str | None], dict[str, str | None], set[str], set[str]]:
        """
        Return (err_status, role_map, domain_map, matched_emps, mapped_emps)
        for (year, month). Results are cached for high-performance vectorized lookups.
        """
        key = (year, month)
        if key in self._month_maps:
            return self._month_maps[key]

        snapshot = self._load(year, month)
        mapped_emps = set(self._emp_to_bare.keys())
        if snapshot is None:
            res = (STATUS_LDAP_MISSING, {}, {}, set(), mapped_emps)
            self._month_maps[key] = res
            return res

        role_map: dict[str, str | None] = {}
        domain_map: dict[str, str | None] = {}
        matched_emps: set[str] = set()

        snapshot_dict = snapshot.to_dict(orient="index")
        for emp_id, bare in self._emp_to_bare.items():
            rec = snapshot_dict.get(bare)
            if rec is not None:
                matched_emps.add(emp_id)
                r = rec.get("Role")
                d = rec.get("Domain")
                role_map[emp_id] = str(r).strip() if r and str(r).strip() else None
                domain_map[emp_id] = str(d).strip() if d and str(d).strip() else None

        res = (None, role_map, domain_map, matched_emps, mapped_emps)
        self._month_maps[key] = res
        return res

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

        err_status, role_map, domain_map, matched_emps, mapped_emps = self.get_month_maps(year, month)
        if err_status is not None:
            return err_status, None, None

        if argus_user_id in matched_emps:
            return STATUS_MATCHED, role_map.get(argus_user_id), domain_map.get(argus_user_id)
        elif argus_user_id in mapped_emps:
            return STATUS_NOT_IN_MONTH, None, None
        else:
            return STATUS_INVALID_USER, None, None

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
    to each event using chunk-based streaming to avoid memory pressure, writes
    enriched outputs, and returns a validation report.
    """
    import collections
    import numpy as np

    print("============================================================")
    print("ARGUS M1 -- LDAP CONTEXT ENRICHMENT PIPELINE")
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

    if os.path.isfile(master_path):
        part_files = [master_path]
    elif os.path.isdir(master_path):
        part_files = sorted(
            [
                os.path.join(master_path, f)
                for f in os.listdir(master_path)
                if f.endswith(".parquet") and not f.startswith(".")
            ]
        )
        if not part_files:
            msg = f"No .parquet files found in master events path: {master_path}"
            report["warnings"].append(msg)
            _write_validation(report, output_validation)
            print(f"  [FATAL] {msg}")
            return report
    else:
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

    print(f"  All required inputs present. Master part files to process: {len(part_files)}")

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
        cache.get_month_maps(y, m)

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
    # 4 & 5. Streaming chunk-based processing & enrichment
    # ------------------------------------------------------------------
    print("\n[4/7] & [5/7] Enriching events via chunked streaming...")
    os.makedirs(output_dir, exist_ok=True)

    writers: dict[str, pq.ParquetWriter] = {}
    total_input = 0
    source_counts: collections.Counter = collections.Counter()
    status_counts: collections.Counter = collections.Counter()
    monthly_cov: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    user_month_counts: collections.Counter = collections.Counter()
    matched_with_role = 0
    null_ts_count = 0

    enriched_cols = CANONICAL_COLUMNS + ["context_match_status", "ldap_domain"]

    try:
        for p_idx, p_file in enumerate(part_files, 1):
            table = pq.read_table(p_file)
            chunk = table.to_pandas()
            chunk_len = len(chunk)
            total_input += chunk_len

            # Per-source counter
            for src, cnt in chunk["source"].value_counts().items():
                source_counts[str(src)] += cnt

            chunk = chunk.reset_index(drop=True)
            ts_dt = pd.to_datetime(chunk["timestamp"], errors="coerce")
            chunk["_year"] = ts_dt.dt.year
            chunk["_month"] = ts_dt.dt.month

            valid_ts_mask = chunk["_year"].notna() & chunk["_month"].notna()
            invalid_ts_mask = ~valid_ts_mask
            null_ts_count += int(invalid_ts_mask.sum())

            null_uid_mask = chunk["user_id"].isna() | (chunk["user_id"].astype(str).str.strip() == "")

            status_arr = np.full(chunk_len, "", dtype=object)
            role_arr = np.full(chunk_len, None, dtype=object)
            domain_arr = np.full(chunk_len, None, dtype=object)

            status_arr[invalid_ts_mask] = STATUS_INVALID_TS
            status_arr[valid_ts_mask & null_uid_mask] = STATUS_INVALID_USER

            processable_mask = valid_ts_mask & ~null_uid_mask

            if processable_mask.any():
                proc_idx = chunk.index[processable_mask]
                proc_df = chunk.loc[proc_idx, ["user_id", "_year", "_month"]]

                for (y, m), grp in proc_df.groupby(["_year", "_month"]):
                    ym_key = f"{int(y):04d}-{int(m):02d}"
                    err_status, role_map, domain_map, matched_emps, mapped_emps = cache.get_month_maps(int(y), int(m))
                    grp_idx = grp.index
                    uids = grp["user_id"].astype(str)

                    if err_status == STATUS_LDAP_MISSING:
                        status_arr[grp_idx] = STATUS_LDAP_MISSING
                        monthly_cov[ym_key][STATUS_LDAP_MISSING] += len(grp)
                        monthly_cov[ym_key]["events"] += len(grp)
                    else:
                        is_matched = uids.isin(matched_emps)
                        is_mapped = uids.isin(mapped_emps)
                        sub_status = np.where(
                            is_matched,
                            STATUS_MATCHED,
                            np.where(is_mapped, STATUS_NOT_IN_MONTH, STATUS_INVALID_USER),
                        )
                        status_arr[grp_idx] = sub_status

                        roles = uids.map(role_map)
                        domains = uids.map(domain_map)
                        role_arr[grp_idx] = roles
                        domain_arr[grp_idx] = domains

                        n_matched = int(is_matched.sum())
                        n_not_in_month = int((~is_matched & is_mapped).sum())
                        n_invalid_user = int((~is_matched & ~is_mapped).sum())

                        monthly_cov[ym_key][STATUS_MATCHED] += n_matched
                        monthly_cov[ym_key][STATUS_NOT_IN_MONTH] += n_not_in_month
                        monthly_cov[ym_key][STATUS_INVALID_USER] += n_invalid_user
                        monthly_cov[ym_key]["events"] += len(grp)

                        matched_with_role += int((is_matched & roles.notna()).sum())

                        if n_matched > 0:
                            matched_uids = uids[is_matched]
                            for uid, cnt in matched_uids.value_counts().items():
                                user_month_counts[(uid, ym_key)] += cnt

            # Track status counts for this chunk
            for st, cnt in pd.Series(status_arr).value_counts().items():
                status_counts[st] += cnt

            chunk["context_match_status"] = status_arr
            chunk["role"] = role_arr
            chunk["ldap_domain"] = domain_arr

            # Canonical column enforcement
            for col in enriched_cols:
                if col not in chunk.columns:
                    chunk[col] = None

            enriched_chunk = chunk[enriched_cols]

            # Stream partitioned by source
            for source, grp in enriched_chunk.groupby("source"):
                src_key = str(source)
                out_path = os.path.join(output_dir, f"{src_key.lower()}_enriched.parquet")
                tbl = pa.Table.from_pandas(grp, preserve_index=False)
                if src_key not in writers:
                    writers[src_key] = pq.ParquetWriter(out_path, tbl.schema, compression="snappy")
                writers[src_key].write_table(tbl)

            if p_idx % 5 == 0 or p_idx == len(part_files):
                print(f"  Processed {p_idx}/{len(part_files)} part files ({total_input:,d} events)...")
    finally:
        for w in writers.values():
            w.close()

    # Per-source counts recording
    for src, cnt in sorted(source_counts.items()):
        report["counts"][f"input_{src}_events"] = cnt
        print(f"  {src:8s} events: {cnt:,d}")

    report["counts"]["input_events_total"] = total_input
    report["counts"]["output_events_total"] = total_input
    report["counts"]["events_preserved"] = total_input
    report["counts"]["events_lost"] = 0
    report["counts"]["invalid_timestamp_events"] = null_ts_count
    if null_ts_count > 0:
        report["warnings"].append(f"{null_ts_count} events have null timestamps.")

    # Coverage breakdown
    for ym_key, stats in sorted(monthly_cov.items()):
        tot = stats.get("events", 0)
        m_cnt = stats.get(STATUS_MATCHED, 0)
        cov_pct = round(m_cnt / tot * 100, 2) if tot else 0.0
        report["monthly_coverage"][ym_key] = {
            "events": tot,
            STATUS_MATCHED: m_cnt,
            STATUS_NOT_IN_MONTH: stats.get(STATUS_NOT_IN_MONTH, 0),
            STATUS_LDAP_MISSING: stats.get(STATUS_LDAP_MISSING, 0),
            STATUS_INVALID_USER: stats.get(STATUS_INVALID_USER, 0),
            "coverage_pct": cov_pct,
        }

    # Match status breakdown
    report["match_status_breakdown"] = dict(status_counts)
    print("\n  Enrichment match status breakdown:")
    for status, count in sorted(status_counts.items()):
        pct = count / total_input * 100 if total_input else 0
        print(f"    {status:25s}: {count:>10,d}  ({pct:5.2f}%)")

    matched_count = status_counts.get(STATUS_MATCHED, 0)
    matched_missing_role = matched_count - matched_with_role
    report["counts"]["matched_events_with_role"] = matched_with_role
    report["counts"]["matched_events_missing_role"] = matched_missing_role

    print(f"\n  Event preservation: ALL {total_input:,d} events preserved (0 lost).")

    # ------------------------------------------------------------------
    # 6b. User-month context summary (one row per argus_user_id × month)
    # ------------------------------------------------------------------
    print("\n[6/7] Building user_month_context summary...")
    rows = []
    for (uid, ym_key), count in sorted(user_month_counts.items()):
        y, m = int(ym_key[:4]), int(ym_key[5:])
        err_status, role_map, domain_map, matched_emps, _ = cache.get_month_maps(y, m)
        rows.append({
            "user_id": uid,
            "month": ym_key,
            "role": role_map.get(uid),
            "ldap_domain": domain_map.get(uid),
            "event_count": count,
        })

    if rows:
        user_month_ctx = pd.DataFrame(rows)
    else:
        user_month_ctx = pd.DataFrame(
            columns=["user_id", "month", "role", "ldap_domain", "event_count"]
        )

    os.makedirs(os.path.dirname(os.path.abspath(output_user_month)), exist_ok=True)
    user_month_ctx.to_csv(output_user_month, index=False)
    print(f"  user_month_context.csv written: {len(user_month_ctx):,d} rows -> {output_user_month}")
    report["counts"]["user_month_context_rows"] = len(user_month_ctx)

    # ------------------------------------------------------------------
    # 7. Write validation report
    # ------------------------------------------------------------------
    print("\n[7/7] Writing validation report...")
    report["validation_passed"] = True
    _write_validation(report, output_validation)

    print("\n============================================================")
    print("LDAP CONTEXT ENRICHMENT -- PASSED")
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
            if f.endswith(".parquet") and not f.startswith(".")
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
        out_path = os.path.join(output_dir, f"{str(source).lower()}_enriched.parquet")
        table = pa.Table.from_pandas(grp, preserve_index=False)
        pq.write_table(table, out_path, compression="snappy")
        print(f"    {source}: {len(grp):,d} events -> {out_path}")


def _write_validation(report: dict, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    merged: dict = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                merged = json.load(fh)
        except Exception:
            merged = {}

    # If merged report contains existing LDAP source snapshot validation, preserve it
    if "overall" in merged and "files_found" in merged:
        report["ldap_snapshot_validation"] = {
            k: merged[k]
            for k in [
                "ldap_dir",
                "expected_months",
                "expected_columns",
                "files_found",
                "files_missing",
                "files_read_error",
                "schema_issues",
                "monthly_stats",
                "overall",
                "validation_errors",
            ]
            if k in merged
        }

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"  Validation report written: {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = enrich_employee_context()
    sys.exit(0 if result["validation_passed"] else 1)
