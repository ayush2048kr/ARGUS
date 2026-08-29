from pyspark.sql import SparkSession

from normalize_events import normalize_events
from create_ids import anonymize_users


def main():
    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName("ARGUS-Data-Pipeline")
        .getOrCreate()
    )

    device_path = "data/raw/device.csv"
    logon_path = "data/raw/logon.csv"

    # Read raw datasets
    device_raw = (
        spark.read
        .option("header", True)
        .csv(device_path)
    )

    logon_raw = (
        spark.read
        .option("header", True)
        .csv(logon_path)
    )

    # Normalize both datasets into the common ARGUS schema
    device_events = normalize_events(
        device_raw,
        "DEVICE"
    )

    logon_events = normalize_events(
        logon_raw,
        "LOGON"
    )

    # Combine normalized events
    combined = device_events.unionByName(
        logon_events
    )

    # Anonymize users consistently across both datasets
    anonymized = anonymize_users(combined)

    print("===================================")
    print("ARGUS DATA PIPELINE")
    print("===================================")

    print("Device events:", device_events.count())
    print("Logon events:", logon_events.count())
    print("Combined events:", combined.count())
    print(
        "Unique ARGUS users:",
        anonymized.select("user_id").distinct().count()
    )

    print("\nSample normalized events:")
    anonymized.show(10, truncate=False)

    # Save processed data
    output_path = "data/processed/argus_events"

    (
        anonymized
        .write
        .mode("overwrite")
        .parquet(output_path)
    )

    print("\nProcessed data saved to:")
    print(output_path)

    spark.stop()


if __name__ == "__main__":
    main()