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


def normalize_device_events(df: DataFrame) -> DataFrame:
    """
    Normalize raw CERT device DataFrame.
    Expected raw columns: id, date, user, pc, activity
    """
    return (
        df.select(
            F.concat(F.lit("ARG-DEVICE-"), F.col("id")).alias("event_id"),
            F.col("user").alias("raw_user_id"),
            F.to_timestamp(F.col("date"), "MM/dd/yyyy HH:mm:ss").alias("timestamp"),
            F.lit("DEVICE").alias("source"),
            F.lit("DEVICE_ACTIVITY").alias("event_type"),
            F.col("activity").alias("action"),
            F.lit(None).cast("string").alias("resource"),
            F.lit(None).cast("string").alias("resource_sensitivity"),
            F.lit(None).cast("string").alias("source_ip"),
            F.lit(None).cast("string").alias("destination"),
            F.col("pc").alias("device_id"),
            F.lit(None).cast("string").alias("location"),
            F.lit(None).cast("string").alias("role"),
            F.lit(None).cast("string").alias("department"),
            F.lit(None).cast("string").alias("work_schedule"),
            F.lit(None).cast("string").alias("access_level"),
            F.lit(None).cast("boolean").alias("is_external"),
        )
    )


def normalize_logon_events(df: DataFrame) -> DataFrame:
    """
    Normalize raw CERT logon DataFrame.
    Expected raw columns: id, date, user, pc, activity
    """
    return (
        df.select(
            F.concat(F.lit("ARG-LOGON-"), F.col("id")).alias("event_id"),
            F.col("user").alias("raw_user_id"),
            F.to_timestamp(F.col("date"), "MM/dd/yyyy HH:mm:ss").alias("timestamp"),
            F.lit("LOGON").alias("source"),
            F.lit("LOGON_ACTIVITY").alias("event_type"),
            F.col("activity").alias("action"),
            F.lit(None).cast("string").alias("resource"),
            F.lit(None).cast("string").alias("resource_sensitivity"),
            F.lit(None).cast("string").alias("source_ip"),
            F.lit(None).cast("string").alias("destination"),
            F.col("pc").alias("device_id"),
            F.lit(None).cast("string").alias("location"),
            F.lit(None).cast("string").alias("role"),
            F.lit(None).cast("string").alias("department"),
            F.lit(None).cast("string").alias("work_schedule"),
            F.lit(None).cast("string").alias("access_level"),
            F.lit(None).cast("boolean").alias("is_external"),
        )
    )


def normalize_http_events(df: DataFrame) -> DataFrame:
    """
    Normalize raw CERT http DataFrame.
    Expected raw columns: id, date, user, pc, url (or raw_event_id, date, user, pc, url)
    """
    id_col = "raw_event_id" if "raw_event_id" in df.columns else "id"
    url_col = "url" if "url" in df.columns else "activity"

    return (
        df.select(
            F.concat(F.lit("ARG-HTTP-"), F.col(id_col)).alias("event_id"),
            F.col("user").alias("raw_user_id"),
            F.to_timestamp(F.col("date"), "MM/dd/yyyy HH:mm:ss").alias("timestamp"),
            F.lit("HTTP").alias("source"),
            F.lit("HTTP_ACTIVITY").alias("event_type"),
            F.lit("VISIT_URL").alias("action"),
            F.trim(F.col(url_col)).alias("resource"),
            F.lit(None).cast("string").alias("resource_sensitivity"),
            F.lit(None).cast("string").alias("source_ip"),
            F.lit(None).cast("string").alias("destination"),
            F.col("pc").alias("device_id"),
            F.lit(None).cast("string").alias("location"),
            F.lit(None).cast("string").alias("role"),
            F.lit(None).cast("string").alias("department"),
            F.lit(None).cast("string").alias("work_schedule"),
            F.lit(None).cast("string").alias("access_level"),
            F.lit(None).cast("boolean").alias("is_external"),
        )
    )


def normalize_events(df: DataFrame, source_name: str) -> DataFrame:
    """
    Dispatch normalization for a given source name (DEVICE, LOGON, HTTP).
    """
    source_upper = source_name.upper()
    if source_upper == "DEVICE":
        return normalize_device_events(df)
    elif source_upper == "LOGON":
        return normalize_logon_events(df)
    elif source_upper == "HTTP":
        return normalize_http_events(df)
    else:
        raise ValueError(f"Unsupported source_name: {source_name}. Must be DEVICE, LOGON, or HTTP.")