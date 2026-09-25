import json
import os
import sys
import uuid
from urllib.parse import urlparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# Ensure PySpark workers use the active python executable and native Hadoop binaries on Windows
os.environ["HADOOP_HOME"] = r"C:\Users\ayush\Downloads"
os.environ["PATH"] = r"C:\Users\ayush\Downloads\bin;" + os.environ.get("PATH", "")
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from create_ids import anonymize_users, create_user_mapping
from normalize_events import (
    ARGUS_COLUMNS,
    normalize_device_events,
    normalize_http_events,
    normalize_logon_events,
)


# ============================================================
# PATH CONFIGURATIONS
# ============================================================

RAW_DEVICE_PATH = "data/raw/device.csv"
RAW_LOGON_PATH = "data/raw/logon.csv"
RAW_HTTP_PATH = "data/raw/http.csv"

URL_CATEGORIES_CONFIG = "data/schema/url_categories.json"

OUTPUT_USER_MAPPING = "data/processed/user_mapping"
OUTPUT_USER_MAPPING_CSV = "data/processed/user_mapping.csv"

OUTPUT_URL_MAPPING = "data/processed/url_class_mapping"
OUTPUT_URL_MAPPING_CSV = "data/processed/url_class_mapping.csv"

OUTPUT_HTTP_ENRICHED = "data/processed/http_enriched_events"
OUTPUT_ALL_EVENTS = "data/processed/argus_all_events"


# ============================================================
# URL CLASSIFICATION HELPERS
# ============================================================

def load_url_categories(config_path=URL_CATEGORIES_CONFIG):
    """
    Load domain-to-category mapping from JSON configuration.
    """
    if not os.path.exists(config_path):
        print(f"WARNING: Categories config not found at {config_path}.")
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        category_data = json.load(f)

    domain_mapping = {}
    for category, domains in category_data.items():
        for domain in domains:
            domain_clean = domain.lower().strip()
            if domain_clean:
                domain_mapping[domain_clean] = category

    return domain_mapping


def extract_domain(url: str) -> str:
    """
    Extract normalized hostname/domain from a raw URL.
    """
    if not url or not isinstance(url, str):
        return ""

    url_str = url.strip()
    if not url_str.startswith("http://") and not url_str.startswith("https://"):
        url_str = "http://" + url_str

    try:
        parsed = urlparse(url_str)
        hostname = parsed.hostname or ""
        hostname = hostname.lower().strip()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        elif hostname.startswith("m."):
            hostname = hostname[2:]
        return hostname
    except Exception:
        return ""


def classify_url(url: str, domain_mapping: dict) -> str:
    """
    Classify a URL deterministically using domain lookup and TLD rules.
    """
    domain = extract_domain(url)
    if not domain:
        return "unknown"

    # 1. Exact match
    if domain in domain_mapping:
        return domain_mapping[domain]

    # 2. Check parent domains (e.g. sub.facebook.com -> facebook.com)
    parts = domain.split(".")
    for i in range(1, len(parts) - 1):
        parent_domain = ".".join(parts[i:])
        if parent_domain in domain_mapping:
            return domain_mapping[parent_domain]

    # 3. Deterministic TLD rules
    if domain.endswith(".gov") or ".gov." in domain or domain.endswith(".mil") or ".mil." in domain:
        return "government"
    if domain.endswith(".edu") or ".edu." in domain or domain.endswith(".ac.uk"):
        return "education"

    # 4. Fallback for unclassified / synthetic domains
    return "unknown"


# ============================================================
# MAIN UNIFIED PIPELINE
# ============================================================

def main():
    print("============================================================")
    print("ARGUS UNIFIED DEVICE + LOGON + HTTP EVENT PIPELINE")
    print("============================================================")

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("ARGUS-Unified-Event-Pipeline")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.default.parallelism", "16")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    # ------------------------------------------------------------
    # 1. READ RAW DATASETS DIRECTLY WITH PYSPARK
    # ------------------------------------------------------------
    print("\n[1/7] Reading raw CSV datasets with PySpark...")

    device_raw = (
        spark.read
        .option("header", True)
        .csv(RAW_DEVICE_PATH)
    )

    logon_raw = (
        spark.read
        .option("header", True)
        .csv(RAW_LOGON_PATH)
    )

    # http.csv is headerless CERT format: raw_event_id, date, user, pc, url
    http_schema = StructType([
        StructField("id", StringType(), False),
        StructField("date", StringType(), False),
        StructField("user", StringType(), False),
        StructField("pc", StringType(), False),
        StructField("url", StringType(), False),
    ])

    http_raw = (
        spark.read
        .schema(http_schema)
        .csv(RAW_HTTP_PATH)
    )

    device_raw_count = device_raw.count()
    logon_raw_count = logon_raw.count()
    http_raw_count = http_raw.count()
    total_raw_count = device_raw_count + logon_raw_count + http_raw_count

    print(f"  -> Raw DEVICE events : {device_raw_count:>10,d}")
    print(f"  -> Raw LOGON events  : {logon_raw_count:>10,d}")
    print(f"  -> Raw HTTP events   : {http_raw_count:>10,d}")
    print(f"  -> Total Raw events  : {total_raw_count:>10,d}")

    # ------------------------------------------------------------
    # 2. CREATE ONE UNIFIED DETERMINISTIC EMP### USER MAPPING
    # ------------------------------------------------------------
    print("\n[2/7] Creating unified deterministic user mapping across all sources...")

    all_raw_users = (
        device_raw.select(F.col("user").alias("raw_user_id"))
        .union(logon_raw.select(F.col("user").alias("raw_user_id")))
        .union(http_raw.select(F.col("user").alias("raw_user_id")))
        .where(F.col("raw_user_id").isNotNull() & (F.col("raw_user_id") != ""))
        .distinct()
    )

    user_mapping = create_user_mapping(all_raw_users)
    user_mapping.cache()

    unique_user_count = user_mapping.count()
    print(f"  -> Total unique ARGUS users mapped: {unique_user_count:,d}")

    # Write user mapping
    os.makedirs(os.path.dirname(OUTPUT_USER_MAPPING), exist_ok=True)
    user_mapping.write.mode("overwrite").parquet(OUTPUT_USER_MAPPING)

    # Also save as single CSV for auditability
    user_mapping_pd = user_mapping.toPandas().sort_values("raw_user_id")
    user_mapping_pd.to_csv(OUTPUT_USER_MAPPING_CSV, index=False)
    print(f"  -> Saved user mapping to {OUTPUT_USER_MAPPING} and {OUTPUT_USER_MAPPING_CSV}")

    # ------------------------------------------------------------
    # 3. EXTRACT AND CLASSIFY UNIQUE URLS DETERMINISTICALLY
    # ------------------------------------------------------------
    print("\n[3/7] Generating deterministic URL class mapping and semantic categories...")

    domain_mapping = load_url_categories(URL_CATEGORIES_CONFIG)
    print(f"  -> Loaded {len(domain_mapping)} domain definitions from {URL_CATEGORIES_CONFIG}")

    # Collect distinct URLs from HTTP
    raw_urls = (
        http_raw
        .select(F.trim(F.col("url")).alias("url"))
        .where(F.col("url").isNotNull() & (F.col("url") != ""))
        .distinct()
        .toPandas()["url"]
        .tolist()
    )

    unique_urls = sorted(list(set(raw_urls)))
    unique_url_count = len(unique_urls)
    print(f"  -> Total unique URLs: {unique_url_count:,d}")

    # Classify each URL
    url_mapping_data = [
        (u, idx, f"class_{idx}", classify_url(u, domain_mapping))
        for idx, u in enumerate(unique_urls)
    ]

    url_mapping_schema = StructType([
        StructField("url", StringType(), False),
        StructField("class_number", IntegerType(), False),
        StructField("class_label", StringType(), False),
        StructField("url_category", StringType(), False),
    ])

    url_mapping_df = spark.createDataFrame(url_mapping_data, schema=url_mapping_schema)
    url_mapping_df.cache()

    # Write URL class mapping
    url_mapping_df.write.mode("overwrite").parquet(OUTPUT_URL_MAPPING)
    
    import pandas as pd
    url_mapping_pd = pd.DataFrame(url_mapping_data, columns=["url", "class_number", "class_label", "url_category"])
    url_mapping_pd.to_csv(OUTPUT_URL_MAPPING_CSV, index=False)
    print(f"  -> Saved URL class mapping to {OUTPUT_URL_MAPPING} and {OUTPUT_URL_MAPPING_CSV}")

    # ------------------------------------------------------------
    # 4. PRESERVE ENRICHED HTTP DATASET KEYED BY EVENT_ID
    # ------------------------------------------------------------
    print("\n[4/7] Generating enriched HTTP dataset (keyed by event_id for future feature engineering)...")

    http_base = (
        http_raw
        .select(
            F.concat(F.lit("ARG-HTTP-"), F.col("id")).alias("event_id"),
            F.col("user").alias("raw_user_id"),
            F.to_timestamp(F.col("date"), "MM/dd/yyyy HH:mm:ss").alias("timestamp"),
            F.lit("HTTP").alias("source"),
            F.lit("HTTP_ACTIVITY").alias("event_type"),
            F.lit("VISIT_URL").alias("action"),
            F.trim(F.col("url")).alias("resource"),
            F.trim(F.col("url")).alias("url"),
            F.col("pc").alias("device_id"),
        )
    )

    # Join with user mapping and URL class mapping
    http_enriched = (
        http_base
        .join(
            user_mapping.select(
                F.col("raw_user_id").alias("_u_raw"),
                F.col("user_id").alias("user_id")
            ),
            http_base["raw_user_id"] == F.col("_u_raw"),
            "left"
        )
        .drop("_u_raw")
        .join(
            url_mapping_df.select(
                F.col("url").alias("_m_url"),
                F.col("class_number"),
                F.col("class_label"),
                F.col("url_category")
            ),
            http_base["url"] == F.col("_m_url"),
            "left"
        )
        .drop("_m_url")
        .select(
            "event_id",
            "user_id",
            "raw_user_id",
            "timestamp",
            "source",
            "event_type",
            "action",
            "resource",
            "device_id",
            "url",
            "class_number",
            "class_label",
            "url_category",
        )
    )

    # Write enriched HTTP dataset
    http_enriched.write.mode("overwrite").parquet(OUTPUT_HTTP_ENRICHED)
    print(f"  -> Saved enriched HTTP dataset to {OUTPUT_HTTP_ENRICHED}")

    # ------------------------------------------------------------
    # 5. NORMALIZE DEVICE, LOGON, HTTP INTO CANONICAL ARGUS SCHEMA
    # ------------------------------------------------------------
    print("\n[5/7] Normalizing DEVICE, LOGON, and HTTP events into 17-field canonical schema...")

    # Normalize DEVICE
    device_norm_raw = normalize_device_events(device_raw)
    device_events = (
        anonymize_users(device_norm_raw, user_mapping)
        .select(ARGUS_COLUMNS)
    )

    # Normalize LOGON
    logon_norm_raw = normalize_logon_events(logon_raw)
    logon_events = (
        anonymize_users(logon_norm_raw, user_mapping)
        .select(ARGUS_COLUMNS)
    )

    # Normalize HTTP (canonical 17 fields only - url_category excluded from canonical schema)
    http_norm_raw = normalize_http_events(http_raw)
    http_events = (
        anonymize_users(http_norm_raw, user_mapping)
        .select(ARGUS_COLUMNS)
    )

    # ------------------------------------------------------------
    # 6. COMBINE ALL EVENTS INTO MASTER CANONICAL DATASET
    # ------------------------------------------------------------
    print("\n[6/7] Combining all normalized events into master canonical dataset (argus_all_events)...")

    argus_all_events = (
        device_events
        .unionByName(logon_events)
        .unionByName(http_events)
    )

    # Write master dataset
    argus_all_events.write.mode("overwrite").parquet(OUTPUT_ALL_EVENTS)
    print(f"  -> Saved master canonical dataset to {OUTPUT_ALL_EVENTS}")

    # ------------------------------------------------------------
    # 7. SUMMARY & VERIFICATION
    # ------------------------------------------------------------
    print("\n[7/7] Master Pipeline Execution Summary:")
    print("============================================================")

    master_df = spark.read.parquet(OUTPUT_ALL_EVENTS)
    master_count = master_df.count()

    print(f"Total Canonical ARGUS Events : {master_count:>12,d}")
    print(f"Expected Total Events        : {total_raw_count:>12,d}")
    print(f"Count Verification           : {'PASSED' if master_count == total_raw_count else 'FAILED'}")

    print("\nPer-Source Event Breakdown:")
    source_counts = master_df.groupBy("source").count().orderBy("source").toPandas()
    for _, row in source_counts.iterrows():
        print(f"  - {row['source']:<10}: {row['count']:>10,d}")

    print(f"\nCanonical Schema Fields ({len(master_df.columns)} fields):")
    for col_name in master_df.columns:
        print(f"  - {col_name}")

    print("\nSample Master Events:")
    master_df.show(5, truncate=False)

    spark.stop()
    print("\nMaster Pipeline Finished Successfully.")


if __name__ == "__main__":
    main()