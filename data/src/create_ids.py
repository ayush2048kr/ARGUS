import os
import sys

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def create_user_mapping(
    raw_users_df: DataFrame,
    raw_user_col: str = "raw_user_id"
) -> DataFrame:
    """
    Create a deterministic mapping from raw user IDs to anonymized ARGUS user IDs (EMP###).
    
    The mapping is deterministically ordered by raw_user_id:
        DTAA/AAA0371 -> EMP001
        DTAA/AAC0344 -> EMP002
        ...
        DTAA/ZAL0996 -> EMP1000
    """
    users = (
        raw_users_df
        .select(F.col(raw_user_col).alias("raw_user_id"))
        .where(F.col("raw_user_id").isNotNull() & (F.col("raw_user_id") != ""))
        .distinct()
    )

    window = Window.orderBy("raw_user_id")

    mapping = (
        users
        .withColumn(
            "user_id",
            F.format_string("EMP%03d", F.row_number().over(window))
        )
    )

    return mapping


def anonymize_users(
    events: DataFrame,
    mapping: DataFrame,
    raw_user_col: str = "raw_user_id",
    keep_raw_user: bool = False
) -> DataFrame:
    """
    Apply shared ARGUS user mapping to events, replacing raw_user_id with user_id.
    """
    mapping_sub = mapping.select(
        F.col("raw_user_id").alias("_map_raw_user"),
        F.col("user_id").alias("_map_user_id")
    )

    joined = events.join(
        mapping_sub,
        events[raw_user_col] == mapping_sub["_map_raw_user"],
        "left"
    )

    if keep_raw_user:
        result = (
            joined
            .withColumn("user_id", F.col("_map_user_id"))
            .drop("_map_raw_user")
            .drop("_map_user_id")
        )
    else:
        result = (
            joined
            .withColumn("user_id", F.col("_map_user_id"))
            .drop(raw_user_col)
            .drop("_map_raw_user")
            .drop("_map_user_id")
        )

    return result