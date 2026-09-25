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
# PATHS & CONSTANTS
# ============================================================

STAGE1_FEATURES_PATH = "data/processed/user_features_stage1_daily.parquet"
MASTER_EVENTS_PATH = "data/processed/argus_all_events"
HTTP_ENRICHED_PATH = "data/processed/http_enriched_events"

EXPECTED_COLUMNS = [
    "user_id",
    "date",
    "login_count_1d",
    "logoff_count_1d",
    "usb_connect_count_1d",
    "usb_session_duration_mean_1d",
    "http_request_count_1d",
    "total_activity_count_1d",
    "distinct_devices_count_1d",
    "off_hours_event_ratio_1d",
    "is_weekend_1d",
    "active_span_hours_1d",
    "cloud_storage_visit_count_1d",
    "file_sharing_visit_count_1d",
    "technology_visit_count_1d",
    "social_media_visit_count_1d",
    "security_visit_count_1d",
    "unknown_url_ratio_1d",
    "distinct_domains_count_1d",
]

INTEGER_NON_NEGATIVE_COLS = [
    "login_count_1d",
    "logoff_count_1d",
    "usb_connect_count_1d",
    "http_request_count_1d",
    "total_activity_count_1d",
    "distinct_devices_count_1d",
    "cloud_storage_visit_count_1d",
    "file_sharing_visit_count_1d",
    "technology_visit_count_1d",
    "social_media_visit_count_1d",
    "security_visit_count_1d",
    "distinct_domains_count_1d",
]


def fail(msg):
    print("\n[STAGE 1 VALIDATION FAILED]")
    print(f"Error: {msg}")
    sys.exit(1)


def validate_stage1_features():
    print("============================================================")
    print("ARGUS M2 STAGE 1: FEATURE VALIDATION SUITE")
    print("============================================================")

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("ARGUS-M2-Stage1-Validation")
        .config("spark.driver.memory", "4g")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    # ------------------------------------------------------------
    # 1. Output Existence
    # ------------------------------------------------------------
    print("\n[1/10] Checking output dataset existence...")
    if not os.path.exists(STAGE1_FEATURES_PATH):
        fail(f"Stage 1 features not found at: {STAGE1_FEATURES_PATH}")
    print(f"  -> Found feature dataset: {STAGE1_FEATURES_PATH}")

    df = spark.read.parquet(STAGE1_FEATURES_PATH)
    total_rows = df.count()
    print(f"  -> Total user-days loaded: {total_rows:,d}")

    # ------------------------------------------------------------
    # 2. Schema Validation
    # ------------------------------------------------------------
    print("\n[2/10] Validating feature schema...")
    actual_columns = df.columns
    if actual_columns != EXPECTED_COLUMNS:
        fail(
            f"Columns mismatch!\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual  : {actual_columns}"
        )
    print(f"  -> Exact 17 features + 2 key columns verified: PASSED")

    # ------------------------------------------------------------
    # 3. Primary Key & Duplicate Check (user_id, date)
    # ------------------------------------------------------------
    print("\n[3/10] Validating primary key uniqueness (user_id, date)...")
    distinct_keys = df.select("user_id", "date").distinct().count()
    if distinct_keys != total_rows:
        fail(f"Duplicate (user_id, date) rows found! Distinct: {distinct_keys}, Total: {total_rows}")
    print(f"  -> Primary key uniqueness (0 duplicates): PASSED")

    null_users = df.where(F.col("user_id").isNull()).count()
    if null_users > 0:
        fail(f"Found {null_users} null user_id rows.")
    
    unique_users = df.select("user_id").distinct().count()
    print(f"  -> Unique users represented: {unique_users:,d}")

    null_dates = df.where(F.col("date").isNull()).count()
    if null_dates > 0:
        fail(f"Found {null_dates} null date rows.")

    date_stats = df.select(F.min("date").alias("min_d"), F.max("date").alias("max_d")).collect()[0]
    print(f"  -> Date range: {date_stats['min_d']} to {date_stats['max_d']}")
    print("  -> User & Date validity: PASSED")

    # ------------------------------------------------------------
    # 4. Non-Negative Integer Bounds
    # ------------------------------------------------------------
    print("\n[4/10] Validating non-negative integer fields...")
    for col in INTEGER_NON_NEGATIVE_COLS:
        neg_count = df.where(F.col(col) < 0).count()
        null_count = df.where(F.col(col).isNull()).count()
        if neg_count > 0:
            fail(f"Column '{col}' contains {neg_count} negative values.")
        if null_count > 0:
            fail(f"Column '{col}' contains {null_count} null values (should be non-null integer).")
    print(f"  -> All {len(INTEGER_NON_NEGATIVE_COLS)} integer feature fields are non-negative and non-null: PASSED")

    # ------------------------------------------------------------
    # 5. Ratio Bounds [0, 1]
    # ------------------------------------------------------------
    print("\n[5/10] Validating ratio feature bounds [0, 1]...")
    for col in ["off_hours_event_ratio_1d", "unknown_url_ratio_1d"]:
        invalid = df.where((F.col(col) < 0.0) | (F.col(col) > 1.0) | F.col(col).isNull()).count()
        if invalid > 0:
            fail(f"Column '{col}' has {invalid} values outside [0, 1] or NULL.")
    print("  -> Ratios within [0, 1]: PASSED")

    # ------------------------------------------------------------
    # 6. Binary Weekend Indicator {0, 1}
    # ------------------------------------------------------------
    print("\n[6/10] Validating is_weekend_1d indicator...")
    invalid_weekend = df.where(~F.col("is_weekend_1d").isin(0, 1)).count()
    if invalid_weekend > 0:
        fail(f"Found {invalid_weekend} invalid is_weekend_1d values.")
    print("  -> is_weekend_1d binary check: PASSED")

    # ------------------------------------------------------------
    # 7. Active Span Hours [0, 24]
    # ------------------------------------------------------------
    print("\n[7/10] Validating active_span_hours_1d bounds [0, 24]...")
    invalid_span = df.where((F.col("active_span_hours_1d") < 0.0) | (F.col("active_span_hours_1d") > 24.0)).count()
    if invalid_span > 0:
        fail(f"Found {invalid_span} active_span_hours_1d values outside [0, 24].")
    print("  -> active_span_hours_1d within [0, 24]: PASSED")

    # ------------------------------------------------------------
    # 8. USB Session Duration Semantics
    # ------------------------------------------------------------
    print("\n[8/10] Validating USB session duration semantics (positive or NULL)...")
    invalid_usb_dur = df.where((F.col("usb_session_duration_mean_1d") <= 0.0)).count()
    if invalid_usb_dur > 0:
        fail(f"Found {invalid_usb_dur} non-positive USB session duration values.")
    
    usb_null_count = df.where(F.col("usb_session_duration_mean_1d").isNull()).count()
    usb_pop_count = df.where(F.col("usb_session_duration_mean_1d").isNotNull()).count()
    print(f"  -> Valid positive USB session days: {usb_pop_count:,d}")
    print(f"  -> Properly preserved NULL USB session days: {usb_null_count:,d}")
    print("  -> USB session duration semantics: PASSED")

    # ------------------------------------------------------------
    # 9. Activity Count Reconciliation with argus_all_events
    # ------------------------------------------------------------
    print("\n[9/10] Reconciling activity counts with master event dataset...")
    master_df = spark.read.parquet(MASTER_EVENTS_PATH)
    expected_total_events = master_df.count()
    sum_stage1_events = df.select(F.sum("total_activity_count_1d")).collect()[0][0]

    print(f"  -> Master dataset total events : {expected_total_events:,d}")
    print(f"  -> Sum of total_activity_count : {sum_stage1_events:,d}")
    if sum_stage1_events != expected_total_events:
        fail(f"Activity count mismatch! Master: {expected_total_events}, Stage 1 sum: {sum_stage1_events}")
    
    sum_logons = df.select(F.sum("login_count_1d")).collect()[0][0]
    expected_logons = master_df.where(F.col("action") == "Logon").count()
    print(f"  -> Logon count check: {sum_logons:,d} vs Expected: {expected_logons:,d}")
    if sum_logons != expected_logons:
        fail(f"Logon count mismatch! Master: {expected_logons}, Stage 1 sum: {sum_logons}")

    sum_usb = df.select(F.sum("usb_connect_count_1d")).collect()[0][0]
    expected_usb = master_df.where((F.col("source") == "DEVICE") & (F.col("action") == "Connect")).count()
    print(f"  -> USB Connect check: {sum_usb:,d} vs Expected: {expected_usb:,d}")
    if sum_usb != expected_usb:
        fail(f"USB connect mismatch! Master: {expected_usb}, Stage 1 sum: {sum_usb}")
    print("  -> Master event count reconciliation: PASSED")

    # ------------------------------------------------------------
    # 10. HTTP Category Reconciliation with http_enriched_events
    # ------------------------------------------------------------
    print("\n[10/10] Reconciling HTTP category counts with http_enriched_events...")
    http_enriched = spark.read.parquet(HTTP_ENRICHED_PATH)
    
    for cat, col_name in [
        ("cloud_storage", "cloud_storage_visit_count_1d"),
        ("file_sharing", "file_sharing_visit_count_1d"),
        ("technology", "technology_visit_count_1d"),
        ("social_media", "social_media_visit_count_1d"),
        ("security", "security_visit_count_1d"),
    ]:
        sum_cat = df.select(F.sum(col_name)).collect()[0][0]
        expected_cat = http_enriched.where(F.col("url_category") == cat).count()
        print(f"  -> Category '{cat}': {sum_cat:,d} vs Expected: {expected_cat:,d}")
        if sum_cat != expected_cat:
            fail(f"Category count mismatch for {cat}: Expected {expected_cat}, got {sum_cat}")
    
    print("  -> HTTP category reconciliation: PASSED")

    spark.stop()

    print("\n============================================================")
    print("ALL STAGE 1 FEATURE VALIDATION CHECKS PASSED (100% SUCCESS)")
    print("============================================================")


if __name__ == "__main__":
    validate_stage1_features()
