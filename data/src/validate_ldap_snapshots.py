"""
validate_ldap_snapshots.py
==========================
ARGUS M1 — Monthly LDAP Snapshot Validation

Validates all 18 expected monthly LDAP CSV files covering
December 2009 through May 2011.

Expected file naming convention (case-insensitive match attempted):
    LDAP/2009-12.csv, LDAP/2010-01.csv, ..., LDAP/2011-05.csv

Expected columns (as documented):
    employee_name, user_id, Domain, Email, Role

Validation checks performed:
    1.  All 18 expected monthly files are present.
    2.  Column names are consistent across files.
    3.  Required fields (user_id) are non-empty.
    4.  No duplicate user_id values within a single monthly snapshot.
    5.  Monthly employee counts and month-over-month changes are reported.
    6.  Missing Role and Domain values are counted and reported.
    7.  Date/month-to-file associations are confirmed.
    8.  Unexpected schema changes are reported.
    9.  Invalid or blank records are flagged.

Design constraints (per M1 spec):
    - An employee absent from a snapshot is noted as a DATA OBSERVATION,
      never as a risk indicator or inferred termination.
    - No values are invented or imputed.
    - Validation results are written to:
        data/processed/context_enrichment_validation.json
      as a structured record for downstream audit.

Run from the repository root:
    python data/src/validate_ldap_snapshots.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LDAP_DIR = "data/raw/LDAP"
OUTPUT_VALIDATION = "data/processed/context_enrichment_validation.json"

# Required columns as observed in the CERT LDAP snapshots
EXPECTED_COLUMNS = ["employee_name", "user_id", "Domain", "Email", "Role"]

# 18 expected monthly snapshots: 2009-12 through 2011-05
_MONTHS = []
y, m = 2009, 12
while (y, m) <= (2011, 5):
    _MONTHS.append((y, m))
    m += 1
    if m > 12:
        m = 1
        y += 1

EXPECTED_MONTHS: list[tuple[int, int]] = _MONTHS  # 18 entries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expected_filename(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}.csv"


def _try_read_csv(path: str) -> tuple[pd.DataFrame | None, str | None]:
    """Try to read a CSV; return (df, None) or (None, error_message)."""
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        return df, None
    except Exception as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

def validate_ldap_snapshots(ldap_dir: str = LDAP_DIR) -> dict:
    """
    Run all LDAP snapshot validation checks.

    Returns a structured validation report dict that is also written to
    OUTPUT_VALIDATION as JSON.
    """
    print("============================================================")
    print("ARGUS M1 — LDAP MONTHLY SNAPSHOT VALIDATION")
    print("============================================================")

    report: dict = {
        "ldap_dir": ldap_dir,
        "expected_months": len(EXPECTED_MONTHS),
        "expected_columns": EXPECTED_COLUMNS,
        "files_found": [],
        "files_missing": [],
        "files_read_error": [],
        "schema_issues": [],
        "monthly_stats": [],
        "overall": {
            "total_rows_across_all_months": 0,
            "total_invalid_user_id_rows": 0,
            "total_duplicate_user_id_rows": 0,
            "total_missing_role": 0,
            "total_missing_domain": 0,
            "column_consistency": "UNKNOWN",
        },
        "validation_passed": False,
        "validation_errors": [],
    }

    # ------------------------------------------------------------------
    # 1. Check that LDAP directory exists at all
    # ------------------------------------------------------------------
    if not os.path.isdir(ldap_dir):
        msg = (
            f"LDAP directory not found: {ldap_dir!r}. "
            "Place the 18 monthly CSV files in data/raw/LDAP/ and re-run."
        )
        print(f"\n[CRITICAL] {msg}")
        report["validation_errors"].append(msg)
        report["validation_passed"] = False
        _write_report(report)
        return report

    print(f"\nLDAP directory found: {ldap_dir}")

    # ------------------------------------------------------------------
    # 2. Inventory files
    # ------------------------------------------------------------------
    print("\n[1/6] Checking for all 18 expected monthly files...")
    found_files: set[str] = {
        f.lower() for f in os.listdir(ldap_dir) if f.endswith(".csv")
    }

    month_results = []
    for y, m in EXPECTED_MONTHS:
        fname = _expected_filename(y, m)
        fpath = os.path.join(ldap_dir, fname)
        exists = fname.lower() in found_files or os.path.isfile(fpath)
        if exists:
            report["files_found"].append(fname)
        else:
            report["files_missing"].append(fname)
            print(f"  [MISSING] {fname}")
            report["validation_errors"].append(f"Missing file: {fname}")
        month_results.append((y, m, fname, fpath, exists))

    found_count = len(report["files_found"])
    missing_count = len(report["files_missing"])
    print(f"  Found: {found_count}/18   Missing: {missing_count}/18")

    if missing_count > 0:
        print(f"\n  WARNING: {missing_count} file(s) missing — "
              "partial validation will continue for present files.")

    # ------------------------------------------------------------------
    # 3. Read and validate each present file
    # ------------------------------------------------------------------
    print("\n[2/6] Reading and validating each monthly snapshot...")

    column_sets: list[list[str]] = []
    prev_user_ids: set[str] | None = None
    prev_label = None

    total_rows = 0
    total_invalid_uid = 0
    total_dup_uid = 0
    total_missing_role = 0
    total_missing_domain = 0

    for y, m, fname, fpath, exists in month_results:
        month_label = f"{y:04d}-{m:02d}"
        if not exists:
            report["monthly_stats"].append({
                "month": month_label,
                "file": fname,
                "status": "MISSING",
            })
            continue

        df, err = _try_read_csv(fpath)
        if err:
            msg = f"{fname}: read error — {err}"
            report["files_read_error"].append(msg)
            report["validation_errors"].append(msg)
            print(f"  [{month_label}] READ ERROR: {err}")
            report["monthly_stats"].append({
                "month": month_label,
                "file": fname,
                "status": "READ_ERROR",
                "error": err,
            })
            continue

        actual_cols = list(df.columns)
        column_sets.append(actual_cols)

        # Check expected columns
        missing_cols = [c for c in EXPECTED_COLUMNS if c not in actual_cols]
        extra_cols = [c for c in actual_cols if c not in EXPECTED_COLUMNS]
        schema_ok = (len(missing_cols) == 0)

        if missing_cols:
            issue = f"{fname}: missing columns {missing_cols}"
            report["schema_issues"].append(issue)
            report["validation_errors"].append(issue)
        if extra_cols:
            issue = f"{fname}: unexpected extra columns {extra_cols}"
            report["schema_issues"].append(issue)

        row_count = len(df)

        # user_id validation
        if "user_id" in df.columns:
            blank_uid_mask = df["user_id"].str.strip().eq("")
            invalid_uid_count = int(blank_uid_mask.sum())

            # Deduplicate within snapshot
            valid_df = df[~blank_uid_mask].copy()
            dup_uid_count = int(valid_df.duplicated(subset=["user_id"]).sum())
            unique_uid_count = int(valid_df["user_id"].nunique())
        else:
            invalid_uid_count = row_count
            dup_uid_count = 0
            unique_uid_count = 0
            valid_df = df.copy()

        # Role and Domain missing values
        if "Role" in df.columns:
            missing_role = int(
                df["Role"].str.strip().eq("").sum() + df["Role"].isna().sum()
            )
        else:
            missing_role = row_count

        if "Domain" in df.columns:
            missing_domain = int(
                df["Domain"].str.strip().eq("").sum() + df["Domain"].isna().sum()
            )
        else:
            missing_domain = row_count

        # Month-over-month change observation
        current_ids = set(valid_df["user_id"].str.strip()) if "user_id" in df.columns else set()
        if prev_user_ids is not None:
            entered = len(current_ids - prev_user_ids)
            departed = len(prev_user_ids - current_ids)
        else:
            entered = None
            departed = None

        stat = {
            "month": month_label,
            "file": fname,
            "status": "OK" if schema_ok else "SCHEMA_ISSUE",
            "row_count": row_count,
            "unique_user_ids": unique_uid_count,
            "blank_user_id_rows": invalid_uid_count,
            "duplicate_user_ids_within_snapshot": dup_uid_count,
            "missing_role_values": missing_role,
            "missing_domain_values": missing_domain,
            "columns_found": actual_cols,
            "missing_columns": missing_cols,
            "extra_columns": extra_cols,
        }
        if entered is not None:
            stat["users_entered_since_prev_month"] = entered
            stat["users_absent_since_prev_month"] = departed
            # NOTE: absence is a data observation only — not a risk indicator.
            stat["absence_note"] = (
                "Employee absence from a snapshot is a data-quality observation. "
                "No inference about termination or behaviour is made."
            )

        report["monthly_stats"].append(stat)

        total_rows += row_count
        total_invalid_uid += invalid_uid_count
        total_dup_uid += dup_uid_count
        total_missing_role += missing_role
        total_missing_domain += missing_domain

        prev_user_ids = current_ids
        prev_label = month_label

        status_str = "OK" if schema_ok else "SCHEMA_ISSUE"
        change_str = ""
        if entered is not None:
            change_str = f"  (+{entered} entered / -{departed} absent)"
        print(
            f"  [{month_label}] {status_str:12s}  "
            f"rows={row_count:5d}  unique_ids={unique_uid_count:5d}  "
            f"blank_uid={invalid_uid_count}  dups={dup_uid_count}  "
            f"missing_role={missing_role}  missing_domain={missing_domain}"
            + change_str
        )

    # ------------------------------------------------------------------
    # 4. Column consistency check
    # ------------------------------------------------------------------
    print("\n[3/6] Checking column consistency across all snapshots...")
    if column_sets:
        first = column_sets[0]
        all_same = all(c == first for c in column_sets)
        report["overall"]["column_consistency"] = "CONSISTENT" if all_same else "INCONSISTENT"
        if not all_same:
            report["validation_errors"].append(
                "Column names are not identical across all monthly LDAP snapshots."
            )
            print("  WARNING: Column names differ across snapshots.")
        else:
            print(f"  Column consistency: CONSISTENT ({first})")
    else:
        report["overall"]["column_consistency"] = "NO_FILES_READ"

    # ------------------------------------------------------------------
    # 5. Summary totals
    # ------------------------------------------------------------------
    report["overall"]["total_rows_across_all_months"] = total_rows
    report["overall"]["total_invalid_user_id_rows"] = total_invalid_uid
    report["overall"]["total_duplicate_user_id_rows"] = total_dup_uid
    report["overall"]["total_missing_role"] = total_missing_role
    report["overall"]["total_missing_domain"] = total_missing_domain

    print("\n[4/6] Overall LDAP snapshot totals:")
    print(f"  Total rows (all months read) : {total_rows:,d}")
    print(f"  Blank user_id rows           : {total_invalid_uid:,d}")
    print(f"  Duplicate user_id (intra)    : {total_dup_uid:,d}")
    print(f"  Missing Role values          : {total_missing_role:,d}")
    print(f"  Missing Domain values        : {total_missing_domain:,d}")

    # ------------------------------------------------------------------
    # 6. Pass/Fail determination
    # ------------------------------------------------------------------
    print("\n[5/6] Determining validation status...")
    hard_failures = [
        e for e in report["validation_errors"]
        if "Missing file:" in e or "read error" in e or "missing columns" in e
    ]
    report["validation_passed"] = (len(hard_failures) == 0)

    status_label = "PASSED" if report["validation_passed"] else "FAILED"
    print(f"  Validation status : {status_label}")
    if hard_failures:
        print(f"  Hard failures     : {len(hard_failures)}")
        for f in hard_failures:
            print(f"    - {f}")

    # ------------------------------------------------------------------
    # 7. Write JSON report
    # ------------------------------------------------------------------
    print("\n[6/6] Writing validation report...")
    _write_report(report)

    print("\n============================================================")
    print(f"LDAP SNAPSHOT VALIDATION — {status_label}")
    print("============================================================")
    if not report["validation_passed"]:
        print("Resolve the hard failures listed above before running enrichment.")
    else:
        print("All present files passed validation.")
    print(f"Detailed report: {OUTPUT_VALIDATION}")

    return report


def _write_report(report: dict, path: str = OUTPUT_VALIDATION) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"  Report written to: {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ldap_dir = sys.argv[1] if len(sys.argv) > 1 else LDAP_DIR
    result = validate_ldap_snapshots(ldap_dir)
    sys.exit(0 if result["validation_passed"] else 1)
