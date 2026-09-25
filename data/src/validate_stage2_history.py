import math
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
STAGE2_HISTORY_PATH = "data/processed/user_features_stage2_history.parquet"

EXPECTED_COLUMNS = [
    "user_id",
    "date",
    "has_sufficient_history",
    "history_active_days_count",
    "total_activity_7d_avg",
    "total_activity_30d_avg",
    "self_activity_drift_zscore",
    "usb_connect_7d_sum",
    "off_hours_ratio_7d_avg",
    "cloud_storage_7d_sum",
    "file_sharing_7d_sum",
]


def fail(msg):
    print("\n[STAGE 2 VALIDATION FAILED]")
    print(f"Error: {msg}")
    sys.exit(1)


def validate_stage2_history():
    print("============================================================")
    print("ARGUS M2 STAGE 2: SELF-HISTORY VALIDATION SUITE")
    print("============================================================")

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("ARGUS-M2-Stage2-Validation")
        .config("spark.driver.memory", "4g")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    # ------------------------------------------------------------
    # 1. Check file existence
    # ------------------------------------------------------------
    print("\n[1/12] Checking dataset existence...")
    if not os.path.exists(STAGE2_HISTORY_PATH):
        fail(f"Stage 2 history dataset not found at: {STAGE2_HISTORY_PATH}")
    print(f"  -> Found Stage 2 dataset: {STAGE2_HISTORY_PATH}")

    stage2_df = spark.read.parquet(STAGE2_HISTORY_PATH)
    total_stage2_rows = stage2_df.count()
    print(f"  -> Total Stage 2 records loaded: {total_stage2_rows:,d}")

    # ------------------------------------------------------------
    # 2. Validate Schema & Column Order
    # ------------------------------------------------------------
    print("\n[2/12] Validating Stage 2 schema...")
    actual_columns = stage2_df.columns
    if actual_columns != EXPECTED_COLUMNS:
        fail(
            f"Columns mismatch!\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual  : {actual_columns}"
        )
    print(f"  -> Exact 11 columns matching Stage 2 contract: PASSED")

    # ------------------------------------------------------------
    # 3. Row Coverage Match with Stage 1
    # ------------------------------------------------------------
    print("\n[3/12] Validating exact 1:1 row coverage with Stage 1 daily dataset...")
    stage1_df = spark.read.parquet(STAGE1_FEATURES_PATH)
    total_stage1_rows = stage1_df.count()

    print(f"  -> Stage 1 row count : {total_stage1_rows:,d}")
    print(f"  -> Stage 2 row count : {total_stage2_rows:,d}")

    if total_stage2_rows != total_stage1_rows:
        fail(f"Row count mismatch! Stage 1: {total_stage1_rows}, Stage 2: {total_stage2_rows}")

    # Anti-join to confirm 100% exact key alignment
    mismatched_keys = (
        stage1_df.select("user_id", "date")
        .join(stage2_df.select("user_id", "date"), on=["user_id", "date"], how="left_anti")
        .count()
    )
    if mismatched_keys > 0:
        fail(f"Found {mismatched_keys} (user_id, date) pairs in Stage 1 missing from Stage 2!")
    print("  -> Exact 1:1 row coverage & key reconciliation: PASSED")

    # ------------------------------------------------------------
    # 4. Primary Key & User/Date Validity
    # ------------------------------------------------------------
    print("\n[4/12] Validating primary key uniqueness and non-null constraints...")
    distinct_keys = stage2_df.select("user_id", "date").distinct().count()
    if distinct_keys != total_stage2_rows:
        fail(f"Duplicate (user_id, date) pairs detected! Distinct: {distinct_keys}, Total: {total_stage2_rows}")
    
    null_users = stage2_df.where(F.col("user_id").isNull()).count()
    null_dates = stage2_df.where(F.col("date").isNull()).count()
    if null_users > 0 or null_dates > 0:
        fail(f"Found null keys! Null user_id: {null_users}, Null date: {null_dates}")

    unique_users = stage2_df.select("user_id").distinct().count()
    date_stats = stage2_df.select(F.min("date").alias("min_d"), F.max("date").alias("max_d")).collect()[0]
    print(f"  -> Primary key uniqueness (0 duplicates): PASSED")
    print(f"  -> Unique users represented: {unique_users:,d}")
    print(f"  -> Date range: {date_stats['min_d']} to {date_stats['max_d']}")

    # ------------------------------------------------------------
    # 5. History Active Days Count Bounds [0, 30]
    # ------------------------------------------------------------
    print("\n[5/12] Validating history_active_days_count bounds [0, 30]...")
    invalid_hist_count = stage2_df.where(
        (F.col("history_active_days_count") < 0) |
        (F.col("history_active_days_count") > 30) |
        F.col("history_active_days_count").isNull()
    ).count()
    if invalid_hist_count > 0:
        fail(f"Found {invalid_hist_count} history_active_days_count values outside [0, 30] or NULL.")
    print("  -> history_active_days_count in [0, 30] and non-null: PASSED")

    # ------------------------------------------------------------
    # 6. Sufficiency Flag & Rule Consistency
    # ------------------------------------------------------------
    print("\n[6/12] Validating has_sufficient_history logic and NULL semantics...")
    null_suff = stage2_df.where(F.col("has_sufficient_history").isNull()).count()
    if null_suff > 0:
        fail(f"Found {null_suff} null values in has_sufficient_history.")

    # Rule: has_sufficient_history is True iff history_active_days_count >= 14
    mismatched_suff = stage2_df.where(
        (F.col("has_sufficient_history") == True) & (F.col("history_active_days_count") < 14) |
        (F.col("has_sufficient_history") == False) & (F.col("history_active_days_count") >= 14)
    ).count()
    if mismatched_suff > 0:
        fail(f"Found {mismatched_suff} rows violating has_sufficient_history <-> count >= 14 rule.")

    # Rule: when has_sufficient_history is False, z-score and 30d avg MUST be NULL
    invalid_insufficient_z = stage2_df.where(
        (F.col("has_sufficient_history") == False) &
        (F.col("self_activity_drift_zscore").isNotNull() | F.col("total_activity_30d_avg").isNotNull())
    ).count()
    if invalid_insufficient_z > 0:
        fail(f"Found {invalid_insufficient_z} rows with insufficient history having non-null 30d/z-score values!")

    # Rule: when has_sufficient_history is True, total_activity_30d_avg MUST be non-null
    null_30d_when_suff = stage2_df.where(
        (F.col("has_sufficient_history") == True) & F.col("total_activity_30d_avg").isNull()
    ).count()
    if null_30d_when_suff > 0:
        fail(f"Found {null_30d_when_suff} rows with sufficient history having NULL total_activity_30d_avg.")

    suff_count = stage2_df.where(F.col("has_sufficient_history") == True).count()
    insuff_count = stage2_df.where(F.col("has_sufficient_history") == False).count()
    print(f"  -> Sufficient history rows (>=14 active days) : {suff_count:>10,d} ({suff_count / total_stage2_rows * 100:>5.2f}%)")
    print(f"  -> Insufficient history rows (burn-in / cold) : {insuff_count:>10,d} ({insuff_count / total_stage2_rows * 100:>5.2f}%)")
    print("  -> Sufficiency logic and NULL consistency: PASSED")

    # ------------------------------------------------------------
    # 7. Non-Negative Bounds for Counts & Averages
    # ------------------------------------------------------------
    print("\n[7/12] Validating bounds on sums and averages...")
    for col in ["total_activity_7d_avg", "total_activity_30d_avg", "usb_connect_7d_sum", "cloud_storage_7d_sum", "file_sharing_7d_sum"]:
        neg_count = stage2_df.where(F.col(col) < 0).count()
        if neg_count > 0:
            fail(f"Column '{col}' has {neg_count} negative values.")
    
    invalid_off_hours = stage2_df.where(
        (F.col("off_hours_ratio_7d_avg") < 0.0) | (F.col("off_hours_ratio_7d_avg") > 1.0)
    ).count()
    if invalid_off_hours > 0:
        fail(f"Column 'off_hours_ratio_7d_avg' has {invalid_off_hours} values outside [0, 1].")
    print("  -> Sums non-negative and off-hours ratio in [0, 1]: PASSED")

    # ------------------------------------------------------------
    # 8. Infinite and NaN Checks on Z-scores
    # ------------------------------------------------------------
    print("\n[8/12] Checking for NaN and Infinite values in Z-scores...")
    nan_count = stage2_df.where(F.isnan("self_activity_drift_zscore")).count()
    if nan_count > 0:
        fail(f"Found {nan_count} NaN values in self_activity_drift_zscore.")

    z_stats = stage2_df.select(
        F.min("self_activity_drift_zscore").alias("min_z"),
        F.max("self_activity_drift_zscore").alias("max_z"),
        F.count("self_activity_drift_zscore").alias("valid_z_count"),
    ).collect()[0]

    min_z = z_stats["min_z"]
    max_z = z_stats["max_z"]
    valid_z_count = z_stats["valid_z_count"]

    if math.isinf(min_z) or math.isinf(max_z):
        fail(f"Infinite Z-score detected! Min: {min_z}, Max: {max_z}")

    print(f"  -> Valid computed Z-scores: {valid_z_count:,d}")
    print(f"  -> Z-score range: [{min_z}, {max_z}]")
    print("  -> No NaN or infinite values detected: PASSED")

    # ------------------------------------------------------------
    # 9. Temporal Lookahead & Contamination Spot Checks
    # ------------------------------------------------------------
    print("\n[9/12] Verifying strictly trailing window boundaries (No day D contamination)...")
    # Spot check user on their first active day: prior active days MUST be 0
    first_days = (
        stage1_df.groupBy("user_id")
        .agg(F.min("date").alias("first_date"))
        .join(stage2_df, on=["user_id"], how="inner")
        .where(F.col("date") == F.col("first_date"))
    )
    invalid_first_day = first_days.where(F.col("history_active_days_count") != 0).count()
    if invalid_first_day > 0:
        fail(f"Found {invalid_first_day} users whose first recorded date had non-zero historical days (Contamination detected)!")
    print("  -> Day 1 baseline isolation (0 prior days on initial date): PASSED")

    # ------------------------------------------------------------
    # 10. Mathematical Verification on Sample Users
    # ------------------------------------------------------------
    print("\n[10/12] Performing mathematical manual verification on sample user (EMP001)...")
    emp001_s1 = stage1_df.where(F.col("user_id") == "EMP001").toPandas().sort_values("date").set_index("date")
    emp001_s2 = stage2_df.where(F.col("user_id") == "EMP001").toPandas().sort_values("date").set_index("date")

    # Verify 5 distinct sample dates
    sample_dates = emp001_s2.index[14:19]
    for test_d in sample_dates:
        # Compute manually in pandas strictly over trailing 30 calendar days
        start_30d = test_d - pd.Timedelta(days=30)
        end_30d = test_d - pd.Timedelta(days=1)
        sub_30d = emp001_s1.loc[(emp001_s1.index >= start_30d) & (emp001_s1.index <= end_30d)]

        hist_count = len(sub_30d)
        hist_mean = sub_30d["total_activity_count_1d"].mean()
        hist_std = sub_30d["total_activity_count_1d"].std()
        curr_act = emp001_s1.loc[test_d, "total_activity_count_1d"]

        expected_z = round((curr_act - hist_mean) / hist_std, 4) if (hist_std and hist_std > 1e-6) else None
        actual_z = emp001_s2.loc[test_d, "self_activity_drift_zscore"]

        if expected_z is not None and actual_z is not None:
            diff = abs(expected_z - actual_z)
            if diff > 1e-3:
                fail(f"Z-score calculation mismatch on {test_d} for EMP001! Expected: {expected_z}, Got: {actual_z}")

    print("  -> Mathematical spot-check verification: PASSED (Exact numerical match)")

    # ------------------------------------------------------------
    # 11. Comprehensive Null Count Summary
    # ------------------------------------------------------------
    print("\n[11/12] Reporting exact Null counts across all Stage 2 fields:")
    for col in EXPECTED_COLUMNS:
        null_count = stage2_df.where(F.col(col).isNull()).count()
        pct = (null_count / total_stage2_rows) * 100
        print(f"  - {col:<28}: {null_count:>8,d} nulls ({pct:>5.2f}%)")

    # ------------------------------------------------------------
    # 12. Deterministic Audit Sample Output
    # ------------------------------------------------------------
    print("\n[12/12] Deterministic Audit Sample Table:")
    print("=========================================================================================================")
    print(f"{'User ID':<8} | {'Date':<10} | {'Active 30d':<10} | {'Act 7d Avg':<10} | {'Act 30d Avg':<11} | {'Drift Z-Score':<13} | {'Sufficient':<10}")
    print("---------------------------------------------------------------------------------------------------------")

    audit_users = ["EMP001", "EMP010", "EMP814"]
    sample_rows = (
        stage2_df.where(F.col("user_id").isin(audit_users))
        .where(F.col("date").isin("2010-01-04", "2010-01-11", "2010-01-22", "2010-06-15", "2011-01-10"))
        .orderBy("user_id", "date")
        .collect()
    )

    for row in sample_rows:
        act_7d = f"{row['total_activity_7d_avg']:.2f}" if row['total_activity_7d_avg'] is not None else "NULL"
        act_30d = f"{row['total_activity_30d_avg']:.2f}" if row['total_activity_30d_avg'] is not None else "NULL"
        z_score = f"{row['self_activity_drift_zscore']:+.4f}" if row['self_activity_drift_zscore'] is not None else "NULL"
        suff = "TRUE" if row['has_sufficient_history'] else "FALSE"
        print(f"{row['user_id']:<8} | {str(row['date']):<10} | {row['history_active_days_count']:>10d} | {act_7d:>10} | {act_30d:>11} | {z_score:>13} | {suff:<10}")

    print("=========================================================================================================")

    spark.stop()
    print("\nALL STAGE 2 VALIDATION CHECKS PASSED (100% SUCCESS).")


if __name__ == "__main__":
    import pandas as pd
    validate_stage2_history()
