import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Ensure PySpark workers use the active python executable and native Hadoop binaries on Windows
os.environ["HADOOP_HOME"] = r"C:\Users\ayush\Downloads"
os.environ["PATH"] = r"C:\Users\ayush\Downloads\bin;" + os.environ.get("PATH", "")
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable


# ============================================================
# PATH CONFIGURATIONS
# ============================================================

INPUT_MASTER_EVENTS = "data/processed/argus_all_events"
INPUT_HTTP_ENRICHED = "data/processed/http_enriched_events"
OUTPUT_STAGE1_FEATURES = "data/processed/user_features_stage1_daily.parquet"


# ============================================================
# STAGE 1 FEATURE EXTRACTION
# ============================================================

def extract_stage1_features():
    print("============================================================")
    print("ARGUS M2 STAGE 1: DAILY USER FEATURE EXTRACTION")
    print("============================================================")

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("ARGUS-M2-Stage1-Feature-Extraction")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.default.parallelism", "16")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    # ------------------------------------------------------------
    # 1. READ INPUT DATASETS
    # ------------------------------------------------------------
    print("\n[1/5] Loading master canonical events and HTTP enrichment...")

    master_df = spark.read.parquet(INPUT_MASTER_EVENTS)
    http_enriched_df = spark.read.parquet(INPUT_HTTP_ENRICHED)

    total_master = master_df.count()
    total_http = http_enriched_df.count()

    print(f"  -> Master events loaded : {total_master:>10,d}")
    print(f"  -> HTTP enriched loaded : {total_http:>10,d}")

    # ------------------------------------------------------------
    # 2. COMPUTE USB SESSION DURATIONS (FIFO PAIRING)
    # ------------------------------------------------------------
    print("\n[2/5] Computing USB session durations with deterministic FIFO pairing...")

    usb_window = Window.partitionBy("user_id", "device_id").orderBy("timestamp")

    device_events = (
        master_df
        .where(F.col("source") == "DEVICE")
        .withColumn("next_action", F.lead("action", 1).over(usb_window))
        .withColumn("next_timestamp", F.lead("timestamp", 1).over(usb_window))
    )

    # Valid paired sessions: Connect immediately followed by Disconnect
    paired_usb = (
        device_events
        .where((F.col("action") == "Connect") & (F.col("next_action") == "Disconnect"))
        .withColumn(
            "duration_minutes",
            (F.unix_timestamp("next_timestamp") - F.unix_timestamp("timestamp")) / 60.0
        )
        .where(F.col("duration_minutes") > 0)
        .withColumn("date", F.to_date("timestamp"))
        .groupBy("user_id", "date")
        .agg(
            F.round(F.mean("duration_minutes"), 4).alias("usb_session_duration_mean_1d")
        )
    )

    paired_usb.cache()
    paired_days_count = paired_usb.count()
    print(f"  -> Distinct (user, date) pairs with valid USB sessions: {paired_days_count:,d}")

    # ------------------------------------------------------------
    # 3. COMPUTE HTTP SEMANTIC CATEGORY & DOMAIN METRICS
    # ------------------------------------------------------------
    print("\n[3/5] Computing HTTP semantic categories & domain metrics...")

    # Extract clean root/hostname domain from URL
    http_prepared = (
        http_enriched_df
        .withColumn("date", F.to_date("timestamp"))
        .withColumn(
            "domain",
            F.lower(F.regexp_extract(F.col("url"), r"^(?:https?://)?(?:www\.|m\.)?([^/:]+)", 1))
        )
    )

    http_daily = (
        http_prepared
        .groupBy("user_id", "date")
        .agg(
            F.sum(F.when(F.col("url_category") == "cloud_storage", 1).otherwise(0)).cast("int").alias("cloud_storage_visit_count_1d"),
            F.sum(F.when(F.col("url_category") == "file_sharing", 1).otherwise(0)).cast("int").alias("file_sharing_visit_count_1d"),
            F.sum(F.when(F.col("url_category") == "technology", 1).otherwise(0)).cast("int").alias("technology_visit_count_1d"),
            F.sum(F.when(F.col("url_category") == "social_media", 1).otherwise(0)).cast("int").alias("social_media_visit_count_1d"),
            F.sum(F.when(F.col("url_category") == "security", 1).otherwise(0)).cast("int").alias("security_visit_count_1d"),
            F.sum(F.when(F.col("url_category") == "unknown", 1).otherwise(0)).alias("_unknown_count"),
            F.count("event_id").alias("_total_http_count"),
            F.countDistinct(
                F.when((F.col("domain").isNotNull()) & (F.col("domain") != ""), F.col("domain"))
            ).cast("int").alias("distinct_domains_count_1d"),
        )
        .withColumn(
            "unknown_url_ratio_1d",
            F.round(F.col("_unknown_count") / F.col("_total_http_count"), 6)
        )
        .drop("_unknown_count", "_total_http_count")
    )

    http_daily.cache()

    # ------------------------------------------------------------
    # 4. COMPUTE BASE BEHAVIORAL & TEMPORAL METRICS FROM MASTER
    # ------------------------------------------------------------
    print("\n[4/5] Computing base behavioral and temporal metrics from master events...")

    master_prepared = master_df.withColumn("date", F.to_date("timestamp"))

    master_daily = (
        master_prepared
        .groupBy("user_id", "date")
        .agg(
            F.sum(F.when(F.col("action") == "Logon", 1).otherwise(0)).cast("int").alias("login_count_1d"),
            F.sum(F.when(F.col("action") == "Logoff", 1).otherwise(0)).cast("int").alias("logoff_count_1d"),
            F.sum(F.when((F.col("source") == "DEVICE") & (F.col("action") == "Connect"), 1).otherwise(0)).cast("int").alias("usb_connect_count_1d"),
            F.sum(F.when(F.col("source") == "HTTP", 1).otherwise(0)).cast("int").alias("http_request_count_1d"),
            F.count("event_id").cast("int").alias("total_activity_count_1d"),
            F.countDistinct("device_id").cast("int").alias("distinct_devices_count_1d"),
            F.sum(
                F.when((F.hour("timestamp") < 8) | (F.hour("timestamp") >= 18), 1).otherwise(0)
            ).alias("_off_hours_count"),
            F.min("timestamp").alias("_min_ts"),
            F.max("timestamp").alias("_max_ts"),
        )
        .withColumn(
            "off_hours_event_ratio_1d",
            F.round(F.col("_off_hours_count") / F.col("total_activity_count_1d"), 6)
        )
        .withColumn(
            "is_weekend_1d",
            F.when(F.dayofweek("date").isin(1, 7), 1).otherwise(0).cast("int")
        )
        .withColumn(
            "active_span_hours_1d",
            F.round((F.unix_timestamp("_max_ts") - F.unix_timestamp("_min_ts")) / 3600.0, 4)
        )
        .drop("_off_hours_count", "_min_ts", "_max_ts")
    )

    # ------------------------------------------------------------
    # 5. ASSEMBLE COMPLETE STAGE 1 FEATURE TABLE
    # ------------------------------------------------------------
    print("\n[5/5] Merging daily features and saving Stage 1 feature table...")

    stage1_features = (
        master_daily
        .join(http_daily, on=["user_id", "date"], how="left")
        .join(paired_usb, on=["user_id", "date"], how="left")
        .select(
            F.col("user_id"),
            F.col("date"),
            F.col("login_count_1d"),
            F.col("logoff_count_1d"),
            F.col("usb_connect_count_1d"),
            F.col("usb_session_duration_mean_1d"),  # Nullable: preserves NULL if no USB session
            F.col("http_request_count_1d"),
            F.col("total_activity_count_1d"),
            F.col("distinct_devices_count_1d"),
            F.col("off_hours_event_ratio_1d"),
            F.col("is_weekend_1d"),
            F.col("active_span_hours_1d"),
            F.coalesce(F.col("cloud_storage_visit_count_1d"), F.lit(0)).cast("int").alias("cloud_storage_visit_count_1d"),
            F.coalesce(F.col("file_sharing_visit_count_1d"), F.lit(0)).cast("int").alias("file_sharing_visit_count_1d"),
            F.coalesce(F.col("technology_visit_count_1d"), F.lit(0)).cast("int").alias("technology_visit_count_1d"),
            F.coalesce(F.col("social_media_visit_count_1d"), F.lit(0)).cast("int").alias("social_media_visit_count_1d"),
            F.coalesce(F.col("security_visit_count_1d"), F.lit(0)).cast("int").alias("security_visit_count_1d"),
            F.coalesce(F.col("unknown_url_ratio_1d"), F.lit(0.0)).alias("unknown_url_ratio_1d"),
            F.coalesce(F.col("distinct_domains_count_1d"), F.lit(0)).cast("int").alias("distinct_domains_count_1d"),
        )
        .orderBy("user_id", "date")
    )

    # Write output to Parquet
    os.makedirs(os.path.dirname(OUTPUT_STAGE1_FEATURES), exist_ok=True)
    stage1_features.write.mode("overwrite").parquet(OUTPUT_STAGE1_FEATURES)

    print(f"\nStage 1 features saved successfully to:\n{OUTPUT_STAGE1_FEATURES}")

    # Summary verification
    result_df = spark.read.parquet(OUTPUT_STAGE1_FEATURES)
    row_count = result_df.count()
    user_count = result_df.select("user_id").distinct().count()

    print("\nStage 1 Extraction Summary:")
    print(f"  -> Total User-Days Extracted : {row_count:>10,d}")
    print(f"  -> Unique Users Represented  : {user_count:>10,d}")
    print(f"  -> Total Features Generated  : {len(result_df.columns) - 2:>10d} (+ 2 key columns)")

    print("\nSample Stage 1 Feature Rows:")
    result_df.show(5, truncate=False)

    spark.stop()
    print("Stage 1 Feature Extraction Complete.")


if __name__ == "__main__":
    extract_stage1_features()
