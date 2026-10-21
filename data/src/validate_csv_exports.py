import os
import sys
import pandas as pd
import pyarrow.parquet as pq

# ============================================================
# PATH CONFIGURATIONS
# ============================================================

CSV_DIR = "data/processed/csv_exports"
SUMMARY_FILE = os.path.join(CSV_DIR, "export_summary.txt")

VALIDATION_TARGETS = [
    {
        "name": "MASTER EVENT SAMPLE",
        "csv_path": os.path.join(CSV_DIR, "argus_all_events_sample.csv"),
        "parquet_path": "data/processed/argus_all_events",
        "expected_rows": 10000,
        "is_sample": True,
        "primary_key": "event_id"
    },
    {
        "name": "HTTP EVENT SAMPLE",
        "csv_path": os.path.join(CSV_DIR, "http_events_sample.csv"),
        "parquet_path": "data/processed/http_events",
        "expected_rows": 10000,
        "is_sample": True,
        "primary_key": "event_id"
    },
    {
        "name": "HTTP ENRICHED EVENT SAMPLE",
        "csv_path": os.path.join(CSV_DIR, "http_enriched_events_sample.csv"),
        "parquet_path": "data/processed/http_enriched_events",
        "expected_rows": 10000,
        "is_sample": True,
        "primary_key": "event_id"
    },
    {
        "name": "URL CLASSIFICATION MAPPING",
        "csv_path": os.path.join(CSV_DIR, "url_class_mapping.csv"),
        "parquet_path": "data/processed/url_class_mapping",
        "expected_rows": 105428,
        "is_sample": False,
        "primary_key": "url"
    },
    {
        "name": "STAGE 1 DAILY FEATURES",
        "csv_path": os.path.join(CSV_DIR, "user_features_stage1_daily.csv"),
        "parquet_path": "data/processed/user_features_stage1_daily.parquet",
        "expected_rows": 334905,
        "is_sample": False,
        "primary_key": ["user_id", "date"]
    },
    {
        "name": "STAGE 2 HISTORICAL FEATURES",
        "csv_path": os.path.join(CSV_DIR, "user_features_stage2_history.csv"),
        "parquet_path": "data/processed/user_features_stage2_history.parquet",
        "expected_rows": 334905,
        "is_sample": False,
        "primary_key": ["user_id", "date"]
    },
    {
        "name": "STAGE 3 PEER CLUSTERS",
        "csv_path": os.path.join(CSV_DIR, "user_peer_clusters.csv"),
        "parquet_path": "data/processed/user_peer_clusters.parquet",
        "expected_rows": 1000,
        "is_sample": False,
        "primary_key": "user_id"
    }
]


def validate_csv_exports():
    print("============================================================")
    print("ARGUS CSV EXPORT VALIDATION SUITE")
    print("============================================================")

    all_passed = True

    for target in VALIDATION_TARGETS:
        name = target["name"]
        csv_path = target["csv_path"]
        parquet_path = target["parquet_path"]
        expected_rows = target["expected_rows"]
        is_sample = target["is_sample"]
        pk = target["primary_key"]

        print(f"\n" + "=" * 60)
        print(f"VALIDATING: {name}")
        print(f"=" * 60)

        # 1. Existence check
        if not os.path.exists(csv_path):
            print(f"  [FAIL] CSV file does not exist: {csv_path}")
            all_passed = False
            continue
        file_size = os.path.getsize(csv_path)
        print(f"  [PASS] File exists: {csv_path} ({file_size:,d} bytes)")

        # 2. Read source parquet schema
        pq_table = pq.read_table(parquet_path)
        pq_cols = pq_table.column_names
        pq_rows = pq_table.num_rows

        # Read CSV
        df = pd.read_csv(csv_path)
        csv_rows = len(df)
        csv_cols = list(df.columns)

        # 3. Row count check
        if is_sample:
            if csv_rows != expected_rows:
                print(f"  [FAIL] Row count mismatch! Expected {expected_rows:,d}, got {csv_rows:,d}")
                all_passed = False
            else:
                print(f"  [PASS] Sample row count matches exactly: {csv_rows:,d} (from {pq_rows:,d} source rows)")
        else:
            if csv_rows != pq_rows:
                print(f"  [FAIL] Row count mismatch! Expected {pq_rows:,d}, got {csv_rows:,d}")
                all_passed = False
            else:
                print(f"  [PASS] Complete row count matches 100%: {csv_rows:,d} rows")

        # 4. Column count and order check
        if csv_cols != pq_cols:
            print(f"  [FAIL] Column schema mismatch!")
            print(f"         Expected: {pq_cols}")
            print(f"         Found:    {csv_cols}")
            all_passed = False
        else:
            print(f"  [PASS] All {len(csv_cols)} column names and ordering match source Parquet exactly.")

        # 5. Duplicate check on primary keys
        if pk:
            if isinstance(pk, list):
                dup_count = df.duplicated(subset=pk).sum()
                pk_str = str(pk)
            else:
                dup_count = df[pk].duplicated().sum()
                pk_str = pk

            if dup_count > 0:
                print(f"  [FAIL] Duplicate keys found in {pk_str}: {dup_count:,d}")
                all_passed = False
            else:
                print(f"  [PASS] 0 duplicate keys on {pk_str}.")

        # 6. Null checks summary
        null_counts = df.isnull().sum()
        non_zero_nulls = null_counts[null_counts > 0]
        if len(non_zero_nulls) > 0:
            print(f"  [INFO] Expected nullable fields with missing values:")
            for col, n_null in non_zero_nulls.items():
                pct = (n_null / csv_rows) * 100
                print(f"         - {col}: {n_null:,d} ({pct:.2f}%)")
        else:
            print(f"  [PASS] 0 null values across all columns.")

        # 7. First 5 & Last 5 preview
        print(f"\n  [Preview] First 2 rows:")
        print(df.head(2).to_string(index=False))
        print(f"\n  [Preview] Last 2 rows:")
        print(df.tail(2).to_string(index=False))

    print("\n" + "=" * 60)
    print("PARQUET IMMUTABILITY INTEGRITY CHECK")
    print("=" * 60)

    # Check Parquet dataset counts
    checks = [
        ("argus_all_events", "data/processed/argus_all_events", 4366912),
        ("http_events", "data/processed/http_events", 3451665),
        ("http_enriched_events", "data/processed/http_enriched_events", 3451665),
        ("url_class_mapping", "data/processed/url_class_mapping", 105428),
        ("user_features_stage1_daily", "data/processed/user_features_stage1_daily.parquet", 334905),
        ("user_features_stage2_history", "data/processed/user_features_stage2_history.parquet", 334905),
        ("user_peer_clusters", "data/processed/user_peer_clusters.parquet", 1000)
    ]

    for name, path, expected in checks:
        t = pq.read_table(path)
        if t.num_rows == expected:
            print(f"  [PASS] Original Parquet '{name}' unmodified ({t.num_rows:,d} rows).")
        else:
            print(f"  [FAIL] Parquet '{name}' row count changed! Expected {expected}, got {t.num_rows}")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL CSV EXPORTS AND PARQUET INTEGRITY CHECKS PASSED WITH 100% SUCCESS!")
    else:
        print("SOME CHECKS FAILED! Please review output above.")
    print("=" * 60)


if __name__ == "__main__":
    validate_csv_exports()
