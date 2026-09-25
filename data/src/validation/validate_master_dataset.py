import json
import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# Ensure PySpark workers use active python executable and native Hadoop binaries on Windows
os.environ["HADOOP_HOME"] = r"C:\Users\ayush\Downloads"
os.environ["PATH"] = r"C:\Users\ayush\Downloads\bin;" + os.environ.get("PATH", "")
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable


# ============================================================
# PATHS & EXPECTED CONSTANTS
# ============================================================

MASTER_DATASET_PATH = "data/processed/argus_all_events"
HTTP_ENRICHED_PATH = "data/processed/http_enriched_events"
USER_MAPPING_PATH = "data/processed/user_mapping"
URL_MAPPING_PATH = "data/processed/url_class_mapping"
EVENT_SCHEMA_PATH = "data/schema/event_schema.json"

EXPECTED_COUNTS = {
    "DEVICE": 65668,
    "LOGON": 849579,
    "HTTP": 3451665,
    "TOTAL": 4366912,
}

EXPECTED_USERS = 1000

CANONICAL_COLUMNS = [
    "event_id",
    "user_id",
    "timestamp",
    "source",
    "event_type",
    "action",
    "resource",
    "resource_sensitivity",
    "source_ip",
    "destination",
    "device_id",
    "location",
    "role",
    "department",
    "work_schedule",
    "access_level",
    "is_external",
]

CONTROLLED_TAXONOMY = {
    "social_media",
    "email",
    "search",
    "news",
    "shopping",
    "finance",
    "cloud_storage",
    "file_sharing",
    "video_entertainment",
    "music_entertainment",
    "technology",
    "productivity",
    "education",
    "travel",
    "security",
    "government",
    "other",
    "unknown",
}


def fail(msg):
    print("\n[VALIDATION FAILED]")
    print(f"Error: {msg}")
    sys.exit(1)


def main():
    print("============================================================")
    print("ARGUS MASTER DATASET & PIPELINE VALIDATION")
    print("============================================================")

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("ARGUS-Master-Validation")
        .config("spark.driver.memory", "4g")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    # ------------------------------------------------------------
    # 1. Check file existence
    # ------------------------------------------------------------
    print("\n[1/6] Checking output directories...")
    for name, path in [
        ("Master Canonical Dataset", MASTER_DATASET_PATH),
        ("HTTP Enriched Dataset", HTTP_ENRICHED_PATH),
        ("User Mapping", USER_MAPPING_PATH),
        ("URL Mapping", URL_MAPPING_PATH),
    ]:
        if not os.path.exists(path):
            fail(f"{name} not found at expected path: {path}")
        print(f"  -> Found {name}: {path}")

    # ------------------------------------------------------------
    # 2. Validate Canonical Schema
    # ------------------------------------------------------------
    print("\n[2/6] Validating Canonical 17-Field ARGUS Schema...")
    master = spark.read.parquet(MASTER_DATASET_PATH)
    actual_columns = master.columns

    if actual_columns != CANONICAL_COLUMNS:
        fail(
            f"Master dataset columns do not match canonical schema.\n"
            f"Expected: {CANONICAL_COLUMNS}\n"
            f"Actual  : {actual_columns}"
        )

    # Verify forbidden enrichment columns are NOT in master schema
    forbidden_cols = {"url_category", "class_number", "class_label"} & set(actual_columns)
    if forbidden_cols:
        fail(f"Forbidden enrichment columns found in canonical schema: {forbidden_cols}")

    print(f"  -> Exact 17 canonical columns verified: PASSED")
    print(f"  -> No enrichment leakage in canonical schema: PASSED")

    # ------------------------------------------------------------
    # 3. Validate Event Counts per Source
    # ------------------------------------------------------------
    print("\n[3/6] Validating Event Counts per Source...")
    total_count = master.count()
    print(f"  -> Total Master Events : {total_count:,d} (Expected: {EXPECTED_COUNTS['TOTAL']:,d})")

    if total_count != EXPECTED_COUNTS["TOTAL"]:
        fail(f"Total event count mismatch: {total_count} != {EXPECTED_COUNTS['TOTAL']}")

    source_counts = {
        row["source"]: row["count"]
        for row in master.groupBy("source").count().collect()
    }

    for source, expected in [("DEVICE", EXPECTED_COUNTS["DEVICE"]), ("LOGON", EXPECTED_COUNTS["LOGON"]), ("HTTP", EXPECTED_COUNTS["HTTP"])]:
        actual = source_counts.get(source, 0)
        print(f"  -> {source:<8} Events : {actual:>10,d} (Expected: {expected:>10,d})")
        if actual != expected:
            fail(f"Source count mismatch for {source}: {actual} != {expected}")

    print("  -> Event counts per source: PASSED")

    # ------------------------------------------------------------
    # 4. Validate User IDs and Anonymization
    # ------------------------------------------------------------
    print("\n[4/6] Validating User IDs and Anonymization...")
    null_users = master.where(F.col("user_id").isNull()).count()
    print(f"  -> Null user_id count: {null_users}")
    if null_users > 0:
        fail(f"Found {null_users} null user_id rows in master dataset.")

    distinct_users = master.select("user_id").distinct().count()
    print(f"  -> Distinct ARGUS users: {distinct_users:,d} (Expected: {EXPECTED_USERS:,d})")
    if distinct_users != EXPECTED_USERS:
        fail(f"Unique user count mismatch: {distinct_users} != {EXPECTED_USERS}")

    invalid_user_format = master.where(~F.col("user_id").rlike("^EMP[0-9]{3,4}$")).count()
    if invalid_user_format > 0:
        fail(f"Found {invalid_user_format} user_id values not matching EMP### pattern.")
    print("  -> User ID format (EMP###) & uniqueness: PASSED")

    # ------------------------------------------------------------
    # 5. Validate Event ID Uniqueness & Prefixes
    # ------------------------------------------------------------
    print("\n[5/6] Validating Event IDs and Timestamps...")
    null_event_ids = master.where(F.col("event_id").isNull()).count()
    if null_event_ids > 0:
        fail(f"Found {null_event_ids} null event_id values.")

    distinct_event_ids = master.select("event_id").distinct().count()
    if distinct_event_ids != total_count:
        fail(f"Duplicate event IDs detected! Distinct: {distinct_event_ids}, Total: {total_count}")
    print(f"  -> Event ID uniqueness (0 duplicates across {total_count:,d} events): PASSED")

    # Prefix checks
    invalid_prefixes = master.where(
        ~F.col("event_id").startswith("ARG-DEVICE-")
        & ~F.col("event_id").startswith("ARG-LOGON-")
        & ~F.col("event_id").startswith("ARG-HTTP-")
    ).count()
    if invalid_prefixes > 0:
        fail(f"Found {invalid_prefixes} event IDs with invalid prefix.")
    print("  -> Event ID prefixes (ARG-DEVICE-, ARG-LOGON-, ARG-HTTP-): PASSED")

    # Timestamp checks
    null_ts = master.where(F.col("timestamp").isNull()).count()
    if null_ts > 0:
        fail(f"Found {null_ts} null timestamp values.")
    ts_stats = master.select(F.min("timestamp").alias("min_ts"), F.max("timestamp").alias("max_ts")).collect()[0]
    print(f"  -> Timestamp Range: {ts_stats['min_ts']} to {ts_stats['max_ts']}")
    print("  -> Timestamp validation: PASSED")

    # ------------------------------------------------------------
    # 6. Validate HTTP Enrichment Dataset
    # ------------------------------------------------------------
    print("\n[6/6] Validating Preserved HTTP Enrichment Dataset...")
    http_enriched = spark.read.parquet(HTTP_ENRICHED_PATH)
    http_enriched_count = http_enriched.count()

    print(f"  -> HTTP Enriched Events : {http_enriched_count:,d} (Expected: {EXPECTED_COUNTS['HTTP']:,d})")
    if http_enriched_count != EXPECTED_COUNTS["HTTP"]:
        fail(f"HTTP enriched count mismatch: {http_enriched_count} != {EXPECTED_COUNTS['HTTP']}")

    # Required enrichment columns
    expected_enrichment_cols = [
        "event_id", "user_id", "raw_user_id", "timestamp", "source",
        "event_type", "action", "resource", "device_id", "url",
        "class_number", "class_label", "url_category"
    ]
    if http_enriched.columns != expected_enrichment_cols:
        fail(
            f"HTTP enriched columns mismatch.\n"
            f"Expected: {expected_enrichment_cols}\n"
            f"Actual  : {http_enriched.columns}"
        )

    # Check key alignment with master dataset
    http_master_ids = master.where(F.col("source") == "HTTP").select("event_id")
    mismatched_keys = (
        http_enriched
        .select("event_id")
        .join(http_master_ids, on="event_id", how="left_anti")
        .count()
    )
    if mismatched_keys > 0:
        fail(f"Found {mismatched_keys} HTTP enriched event_ids not present in master dataset!")
    print("  -> Primary key alignment (event_id join with master dataset): PASSED")

    # Check taxonomy compliance
    categories = [row["url_category"] for row in http_enriched.select("url_category").distinct().collect()]
    invalid_cats = set(categories) - CONTROLLED_TAXONOMY
    if invalid_cats:
        fail(f"Invalid url_category values found: {invalid_cats}")
    print(f"  -> Taxonomy compliance ({len(categories)} categories present): PASSED")

    # Check nulls in critical enrichment fields
    null_cats = http_enriched.where(F.col("url_category").isNull()).count()
    if null_cats > 0:
        fail(f"Found {null_cats} null url_category values.")
    print("  -> Enrichment non-null checks: PASSED")

    spark.stop()

    print("\n============================================================")
    print("ALL MASTER PIPELINE VALIDATION CHECKS PASSED (100% SUCCESS)")
    print("============================================================")


if __name__ == "__main__":
    main()
