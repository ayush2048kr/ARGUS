from pyspark.sql import DataFrame
from pyspark.sql import functions as F


ARGUS_COLUMNS = [
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


def normalize_events(df: DataFrame, source_name: str) -> DataFrame:
    """
    Normalize a raw CERT device/logon DataFrame
    into the common ARGUS event schema.

    Expected raw columns:
        id, date, user, pc, activity
    """

    if source_name not in {"DEVICE", "LOGON"}:
        raise ValueError("source_name must be either DEVICE or LOGON")

    required_columns = {"id", "date", "user", "pc", "activity"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    normalized = (
        df.select(
            F.col("id").alias("raw_event_id"),
            F.to_timestamp(
                F.col("date"),
                "MM/dd/yyyy HH:mm:ss"
            ).alias("timestamp"),
            F.col("user").alias("raw_user_id"),
            F.col("pc").alias("device_id"),
            F.col("activity").alias("action"),
        )
        .withColumn("source", F.lit(source_name))
        .withColumn(
            "event_type",
            F.when(
                F.col("source") == "DEVICE",
                F.lit("DEVICE_ACTIVITY")
            ).otherwise(
                F.lit("LOGON_ACTIVITY")
            )
        )
        .withColumn("resource", F.lit(None).cast("string"))
        .withColumn(
            "resource_sensitivity",
            F.lit(None).cast("string")
        )
        .withColumn("source_ip", F.lit(None).cast("string"))
        .withColumn("destination", F.lit(None).cast("string"))
        .withColumn("location", F.lit(None).cast("string"))
        .withColumn("role", F.lit(None).cast("string"))
        .withColumn("department", F.lit(None).cast("string"))
        .withColumn("work_schedule", F.lit(None).cast("string"))
        .withColumn("access_level", F.lit(None).cast("string"))
        .withColumn(
            "is_external",
            F.lit(None).cast("boolean")
        )
        .withColumn(
            "event_id",
            F.concat(
                F.lit("ARG-RAW-"),
                F.col("raw_event_id")
            )
        )
        .withColumn(
            "user_id",
            F.col("raw_user_id")
        )
        .select(ARGUS_COLUMNS)
    )

    return normalized