import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Ensure PySpark workers use active python executable and native Hadoop binaries on Windows
os.environ["HADOOP_HOME"] = r"C:\Users\ayush\Downloads"
os.environ["PATH"] = r"C:\Users\ayush\Downloads\bin;" + os.environ.get("PATH", "")
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable


# ============================================================
# PATH CONFIGURATIONS
# ============================================================

INPUT_STAGE1_FEATURES = "data/processed/user_features_stage1_daily.parquet"
OUTPUT_STAGE2_HISTORY = "data/processed/user_features_stage2_history.parquet"


# ============================================================
# STAGE 2 HISTORY & DRIFT EXTRACTION
# ============================================================

def extract_stage2_history():
    print("============================================================")
    print("ARGUS M2 STAGE 2: USER SELF-HISTORY & DRIFT EXTRACTION")
    print("============================================================")

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("ARGUS-M2-Stage2-History-Extraction")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.default.parallelism", "16")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    # ------------------------------------------------------------
    # 1. READ STAGE 1 DAILY FEATURES
    # ------------------------------------------------------------
    print("\n[1/4] Loading Stage 1 daily feature dataset...")

    stage1_df = spark.read.parquet(INPUT_STAGE1_FEATURES)
    total_stage1_rows = stage1_df.count()
    print(f"  -> Stage 1 daily records loaded: {total_stage1_rows:>10,d}")

    # ------------------------------------------------------------
    # 2. DEFINE CALENDAR RANGE WINDOWS (STRICT TRAILING ONLY)
    # ------------------------------------------------------------
    print("\n[2/4] Defining strictly trailing historical windows ([D-7, D-1] and [D-30, D-1])...")

    # Convert calendar date to continuous day index
    stage1_indexed = stage1_df.withColumn(
        "day_idx",
        F.datediff(F.col("date"), F.lit("2010-01-01"))
    )

    # 30-day trailing window: strictly [D - 30, D - 1] (excludes day D = 0)
    w_30d = (
        Window.partitionBy("user_id")
        .orderBy("day_idx")
        .rangeBetween(-30, -1)
    )

    # 7-day trailing window: strictly [D - 7, D - 1] (excludes day D = 0)
    w_7d = (
        Window.partitionBy("user_id")
        .orderBy("day_idx")
        .rangeBetween(-7, -1)
    )

    # ------------------------------------------------------------
    # 3. COMPUTE TRAILING METRICS & SELF-DRIFT Z-SCORE
    # ------------------------------------------------------------
    print("\n[3/4] Computing self-historical baselines, sufficiency flags, and drift Z-scores...")

    # Aggregations over trailing windows
    computed = (
        stage1_indexed
        # 30-day baseline stats
        .withColumn("active_30d", F.count("date").over(w_30d).cast("int"))
        .withColumn("mean_30d_act", F.mean("total_activity_count_1d").over(w_30d))
        .withColumn("std_30d_act", F.stddev("total_activity_count_1d").over(w_30d))
        # 7-day trailing stats
        .withColumn("active_7d", F.count("date").over(w_7d).cast("int"))
        .withColumn("mean_7d_act", F.mean("total_activity_count_1d").over(w_7d))
        .withColumn("sum_7d_usb", F.sum("usb_connect_count_1d").over(w_7d).cast("int"))
        .withColumn("mean_7d_off_hours", F.mean("off_hours_event_ratio_1d").over(w_7d))
        .withColumn("sum_7d_cloud", F.sum("cloud_storage_visit_count_1d").over(w_7d).cast("int"))
        .withColumn("sum_7d_file_sharing", F.sum("file_sharing_visit_count_1d").over(w_7d).cast("int"))
    )

    # Apply sufficiency rules, deterministic edge-case handling, and NULL semantics
    stage2_df = (
        computed
        .withColumn(
            "has_sufficient_history",
            F.when(F.col("active_30d") >= 14, True).otherwise(False)
        )
        .withColumn(
            "history_active_days_count",
            F.col("active_30d")
        )
        .withColumn(
            "total_activity_7d_avg",
            F.when(F.col("active_7d") >= 3, F.round(F.col("mean_7d_act"), 4)).otherwise(F.lit(None).cast("double"))
        )
        .withColumn(
            "total_activity_30d_avg",
            F.when(F.col("active_30d") >= 14, F.round(F.col("mean_30d_act"), 4)).otherwise(F.lit(None).cast("double"))
        )
        .withColumn(
            "self_activity_drift_zscore",
            F.when(
                F.col("active_30d") < 14,
                F.lit(None).cast("double")
            ).when(
                (F.col("std_30d_act").isNull()) | (F.col("std_30d_act") < 1e-6),
                F.when(F.col("total_activity_count_1d") == F.col("mean_30d_act"), F.lit(0.0)).otherwise(F.lit(None).cast("double"))
            ).otherwise(
                F.round((F.col("total_activity_count_1d") - F.col("mean_30d_act")) / F.col("std_30d_act"), 4)
            )
        )
        .withColumn(
            "usb_connect_7d_sum",
            F.when(F.col("active_7d") > 0, F.col("sum_7d_usb")).otherwise(F.lit(None).cast("int"))
        )
        .withColumn(
            "off_hours_ratio_7d_avg",
            F.when(F.col("active_7d") >= 3, F.round(F.col("mean_7d_off_hours"), 4)).otherwise(F.lit(None).cast("double"))
        )
        .withColumn(
            "cloud_storage_7d_sum",
            F.when(F.col("active_7d") > 0, F.col("sum_7d_cloud")).otherwise(F.lit(None).cast("int"))
        )
        .withColumn(
            "file_sharing_7d_sum",
            F.when(F.col("active_7d") > 0, F.col("sum_7d_file_sharing")).otherwise(F.lit(None).cast("int"))
        )
        .select(
            F.col("user_id"),
            F.col("date"),
            F.col("has_sufficient_history"),
            F.col("history_active_days_count"),
            F.col("total_activity_7d_avg"),
            F.col("total_activity_30d_avg"),
            F.col("self_activity_drift_zscore"),
            F.col("usb_connect_7d_sum"),
            F.col("off_hours_ratio_7d_avg"),
            F.col("cloud_storage_7d_sum"),
            F.col("file_sharing_7d_sum"),
        )
        .orderBy("user_id", "date")
    )

    # ------------------------------------------------------------
    # 4. SAVE STAGE 2 FEATURE TABLE
    # ------------------------------------------------------------
    print("\n[4/4] Writing Stage 2 feature dataset to Parquet...")

    os.makedirs(os.path.dirname(OUTPUT_STAGE2_HISTORY), exist_ok=True)
    stage2_df.write.mode("overwrite").parquet(OUTPUT_STAGE2_HISTORY)

    print(f"\nStage 2 features saved successfully to:\n{OUTPUT_STAGE2_HISTORY}")

    # Summary verification
    result_df = spark.read.parquet(OUTPUT_STAGE2_HISTORY)
    row_count = result_df.count()
    user_count = result_df.select("user_id").distinct().count()
    sufficient_count = result_df.where(F.col("has_sufficient_history") == True).count()
    insufficient_count = result_df.where(F.col("has_sufficient_history") == False).count()

    print("\nStage 2 Extraction Summary:")
    print(f"  -> Total Observations Extracted : {row_count:>10,d} (Stage 1 match: {row_count == total_stage1_rows})")
    print(f"  -> Unique Users Represented     : {user_count:>10,d}")
    print(f"  -> Sufficient History Days (>=14): {sufficient_count:>10,d} ({sufficient_count / row_count * 100:>5.2f}%)")
    print(f"  -> Cold-Start Insufficient Days : {insufficient_count:>10,d} ({insufficient_count / row_count * 100:>5.2f}%)")

    print("\nSample Stage 2 Feature Rows:")
    result_df.show(5, truncate=False)

    spark.stop()
    print("Stage 2 Self-History Extraction Complete.")


if __name__ == "__main__":
    extract_stage2_history()
