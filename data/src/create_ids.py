from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def create_user_mapping(events: DataFrame) -> DataFrame:
    """
    Create a deterministic mapping between the raw user ID
    and the anonymized ARGUS user ID.

    Example:
        DTAA/RES0962 -> EMP001
        DTAA/BJC0569 -> EMP002
    """

    users = (
        events
        .select("user_id")
        .where(F.col("user_id").isNotNull())
        .distinct()
    )

    window = Window.orderBy("user_id")

    mapping = (
        users
        .withColumn(
            "argus_user_id",
            F.concat(
                F.lit("EMP"),
                F.lpad(
                    F.row_number().over(window).cast("string"),
                    3,
                    "0"
                )
            )
        )
    )

    return mapping


def anonymize_users(events: DataFrame) -> DataFrame:
    """
    Replace raw dataset user IDs with ARGUS anonymized IDs.
    """

    mapping = create_user_mapping(events)

    # Rename mapping column so the join does not create
    # duplicate user_id columns.
    mapping = mapping.withColumnRenamed(
        "user_id",
        "raw_user_id"
    )

    anonymized = (
        events
        .join(
            mapping,
            events["user_id"] == mapping["raw_user_id"],
            "left"
        )
        .drop("raw_user_id")
        .drop(events["user_id"])
        .withColumnRenamed(
            "argus_user_id",
            "user_id"
        )
    )

    return anonymized