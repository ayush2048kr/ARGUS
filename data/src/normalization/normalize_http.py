import os
import uuid

import dask.dataframe as dd


INPUT_PATH = "data/processed/http_events"
OUTPUT_PATH = "data/processed/http_argus_events"


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


REQUIRED_INPUT_COLUMNS = [
    "event_id",
    "timestamp",
    "source",
    "event_type",
    "action",
    "resource",
    "raw_user_id",
    "device_id",
]


def create_temp_path():
    return os.path.join(
        "data",
        "processed",
        f"http_argus_events_tmp_{uuid.uuid4().hex[:8]}",
    )


def normalize_partition(df):
    """
    Normalize one Dask partition into the ARGUS common schema.
    """

    # -----------------------------------------------------
    # Core fields
    # -----------------------------------------------------

    df["user_id"] = df["raw_user_id"]

    # -----------------------------------------------------
    # Fields unavailable in the HTTP source
    #
    # These remain NULL because the HTTP dataset does not
    # provide this information.
    # -----------------------------------------------------

    df["resource_sensitivity"] = None
    df["source_ip"] = None
    df["destination"] = None
    df["location"] = None
    df["role"] = None
    df["department"] = None
    df["work_schedule"] = None
    df["access_level"] = None
    df["is_external"] = None

    # -----------------------------------------------------
    # Explicit string types
    # -----------------------------------------------------

    string_columns = [
        "event_id",
        "user_id",
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
    ]

    for column in string_columns:
        df[column] = df[column].astype("string")

    # -----------------------------------------------------
    # Timestamp
    # -----------------------------------------------------

    df["timestamp"] = df["timestamp"].astype(
        "datetime64[ns]"
    )

    # -----------------------------------------------------
    # Boolean
    # -----------------------------------------------------

    df["is_external"] = df["is_external"].astype(
        "boolean"
    )

    return df


def main():

    print("===================================")
    print("ARGUS HTTP SCHEMA NORMALIZATION")
    print("===================================")

    # =====================================================
    # 1. Check input
    # =====================================================

    print("\nChecking processed HTTP data...")

    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(
            f"Input HTTP data not found: {INPUT_PATH}"
        )

    print("Input found:", INPUT_PATH)

    # =====================================================
    # 2. Read processed HTTP data
    # =====================================================

    print("\nReading HTTP events with Dask...")

    http = dd.read_parquet(
        INPUT_PATH,
        engine="pyarrow",
    )

    input_count = http.shape[0].compute()

    print("Input HTTP events:", input_count)

    # =====================================================
    # 3. Validate input columns
    # =====================================================

    missing_columns = [
        column
        for column in REQUIRED_INPUT_COLUMNS
        if column not in http.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required HTTP columns: "
            + ", ".join(missing_columns)
        )

    print("Input column check: PASSED")

    # =====================================================
    # 4. Select source columns
    # =====================================================

    print("\nConverting HTTP events to ARGUS schema...")

    normalized = http[
        [
            "event_id",
            "timestamp",
            "source",
            "event_type",
            "action",
            "resource",
            "raw_user_id",
            "device_id",
        ]
    ].copy()

    # =====================================================
    # 5. Apply normalization partition-by-partition
    # =====================================================

    normalized = normalized.map_partitions(
        normalize_partition
    )

    # =====================================================
    # 6. Select final ARGUS schema
    # =====================================================

    normalized = normalized[
        ARGUS_COLUMNS
    ]

    # =====================================================
    # 7. Verify event count
    # =====================================================

    print("\nVerifying event count...")

    output_count = normalized.shape[0].compute()

    print(
        "Output ARGUS events:",
        output_count,
    )

    if input_count != output_count:
        raise RuntimeError(
            f"Event count mismatch!\n"
            f"Input: {input_count}\n"
            f"Output: {output_count}"
        )

    print("Event count verification: PASSED")

    # =====================================================
    # 8. Verify schema
    # =====================================================

    print("\nVerifying ARGUS schema...")

    actual_columns = normalized.columns.tolist()

    if actual_columns != ARGUS_COLUMNS:
        raise RuntimeError(
            "\nARGUS schema mismatch!\n"
            f"Expected: {ARGUS_COLUMNS}\n"
            f"Actual: {actual_columns}"
        )

    print("ARGUS schema verification: PASSED")

    # =====================================================
    # 9. Display sample
    # =====================================================

    print(
        "\nSample normalized ARGUS HTTP events:"
    )

    print(
        normalized
        .head(5)
        .to_string(index=False)
    )

    # =====================================================
    # 10. Prepare temporary output
    # =====================================================

    print("\nPreparing output...")

    os.makedirs(
        "data/processed",
        exist_ok=True,
    )

    temp_path = create_temp_path()

    print(
        "Temporary output:",
        temp_path,
    )

    # =====================================================
    # 11. Write normalized data
    # =====================================================

    print(
        "\nWriting normalized ARGUS events..."
    )

    normalized.to_parquet(
        temp_path,
        engine="pyarrow",
        compression="snappy",
        write_index=False,
        overwrite=True,
    )

    print("Parquet write: COMPLETE")

    # =====================================================
    # 12. Verify written data
    # =====================================================

    print("\nVerifying written output...")

    written = dd.read_parquet(
        temp_path,
        engine="pyarrow",
    )

    written_count = written.shape[0].compute()

    print(
        "Written ARGUS events:",
        written_count,
    )

    if written_count != input_count:
        raise RuntimeError(
            f"Written event count mismatch!\n"
            f"Expected: {input_count}\n"
            f"Written: {written_count}"
        )

    written_columns = written.columns.tolist()

    if written_columns != ARGUS_COLUMNS:
        raise RuntimeError(
            "Written Parquet schema does not match "
            "ARGUS schema."
        )

    print(
        "Written output verification: PASSED"
    )

    # =====================================================
    # 13. Finalize output
    # =====================================================

    print("\nFinalizing output...")

    if os.path.exists(OUTPUT_PATH):

        old_path = (
            OUTPUT_PATH
            + "_old_"
            + uuid.uuid4().hex[:8]
        )

        print(
            "Existing output found."
        )

        print(
            "Moving existing output to:",
            old_path,
        )

        try:
            os.rename(
                OUTPUT_PATH,
                old_path,
            )

        except PermissionError as exc:

            print(
                "\nERROR: Existing output is locked."
            )

            print(
                "Close any program using:"
            )

            print(OUTPUT_PATH)

            raise exc

    os.rename(
        temp_path,
        OUTPUT_PATH,
    )

    print(
        "Output successfully written to:",
        OUTPUT_PATH,
    )

    # =====================================================
    # 14. Final result
    # =====================================================

    print("\n===================================")
    print("HTTP NORMALIZATION COMPLETE")
    print("===================================")

    print(
        "Input HTTP events:",
        input_count,
    )

    print(
        "Output ARGUS events:",
        written_count,
    )

    print(
        "ARGUS schema fields:",
        len(ARGUS_COLUMNS),
    )

    print(
        "Output:",
        OUTPUT_PATH,
    )

    print(
        "\nAll HTTP normalization checks PASSED."
    )


if __name__ == "__main__":
    main()