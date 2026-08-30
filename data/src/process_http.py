import os
import shutil
import uuid

import dask.dataframe as dd
import pandas as pd


# ============================================================
# ARGUS HTTP DATA PROCESSING
# ============================================================

INPUT_PATH = "data/raw/http.csv"

OUTPUT_EVENTS = "data/processed/http_events"
OUTPUT_URLS = "data/processed/url_class_mapping"

RAW_COLUMNS = [
    "raw_event_id",
    "raw_timestamp",
    "raw_user_id",
    "device_id",
    "url",
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def create_temp_output(final_path):
    """
    Create a unique temporary output directory.

    This avoids deleting existing directories, which can cause
    Windows/OneDrive permission errors.
    """

    parent = os.path.dirname(final_path)

    os.makedirs(parent, exist_ok=True)

    temp_name = os.path.basename(final_path) + "_tmp_" + uuid.uuid4().hex[:8]

    temp_path = os.path.join(parent, temp_name)

    os.makedirs(temp_path, exist_ok=True)

    return temp_path


def replace_output_directory(temp_path, final_path):
    """
    Replace the final output directory with the newly created
    temporary directory.

    If the existing directory cannot be removed because it is
    locked by OneDrive or another process, the function reports
    the problem instead of crashing during the processing step.
    """

    if os.path.exists(final_path):

        backup_path = (
            final_path
            + "_old_"
            + uuid.uuid4().hex[:8]
        )

        print(
            f"Existing output found: {final_path}"
        )

        print(
            f"Temporarily moving existing output to: {backup_path}"
        )

        try:

            os.rename(
                final_path,
                backup_path
            )

        except PermissionError:

            print(
                "\nWARNING: Existing output directory is locked."
            )

            print(
                "Please close VS Code/file explorers using the folder"
            )

            print(
                "and make sure OneDrive is not currently syncing it."
            )

            print(
                f"\nNew output remains available at:\n{temp_path}"
            )

            return False

        except OSError as error:

            print(
                "\nWARNING: Could not move existing output directory."
            )

            print(
                f"Reason: {error}"
            )

            print(
                f"\nNew output remains available at:\n{temp_path}"
            )

            return False

    try:

        os.rename(
            temp_path,
            final_path
        )

        print(
            f"Output successfully written to: {final_path}"
        )

        return True

    except OSError as error:

        print(
            "\nWARNING: Could not rename temporary output."
        )

        print(
            f"Reason: {error}"
        )

        print(
            f"\nTemporary output remains at:\n{temp_path}"
        )

        return False


# ============================================================
# MAIN PROCESSING PIPELINE
# ============================================================

def main():

    print("===================================")
    print("ARGUS HTTP PROCESSING - DASK")
    print("===================================")

    # --------------------------------------------------------
    # 1. Read raw HTTP data
    # --------------------------------------------------------

    print("\nReading HTTP data with Dask...")

    http = dd.read_csv(
        INPUT_PATH,
        header=None,
        names=RAW_COLUMNS,
        dtype="string",
        blocksize="64MB",
    )

    raw_events = (
        http.shape[0]
        .compute()
    )

    print(
        "Raw HTTP events:",
        raw_events
    )

    # --------------------------------------------------------
    # 2. Normalize HTTP events
    # --------------------------------------------------------

    print("\nNormalizing HTTP events...")

    http["timestamp"] = dd.to_datetime(
        http["raw_timestamp"],
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce",
    )

    http["event_id"] = (
        "ARG-HTTP-"
        + http["raw_event_id"].astype("string")
    )

    http["source"] = "HTTP"

    http["event_type"] = "HTTP_ACTIVITY"

    http["action"] = "VISIT_URL"

    http["resource"] = http["url"]

    events = http[
        [
            "event_id",
            "timestamp",
            "source",
            "event_type",
            "action",
            "resource",
            "raw_user_id",
            "device_id",
            "url",
        ]
    ]

    normalized_events = (
        events.shape[0]
        .compute()
    )

    print(
        "Normalized HTTP events:",
        normalized_events
    )

    # --------------------------------------------------------
    # 3. Clean URLs
    # --------------------------------------------------------

    print("\nProcessing URLs...")

    events["url"] = (
        events["url"]
        .astype("string")
        .str.strip()
    )

    events = events[
        events["url"].notnull()
        & (events["url"] != "")
    ]

    # --------------------------------------------------------
    # 4. Extract unique URLs
    # --------------------------------------------------------

    print("Finding unique URLs...")

    unique_urls_df = (
        events[["url"]]
        .drop_duplicates()
        .compute()
    )

    unique_urls_df = (
        unique_urls_df
        .sort_values(
            "url",
            kind="mergesort"
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # 5. Create deterministic URL classes
    # --------------------------------------------------------

    print("\nCreating deterministic URL classes...")

    unique_urls_df["class_number"] = (
        unique_urls_df.index
    )

    unique_urls_df["class_label"] = (
        "class_"
        + unique_urls_df[
            "class_number"
        ].astype(str)
    )

    url_mapping = unique_urls_df[
        [
            "url",
            "class_number",
            "class_label",
        ]
    ]

    unique_url_count = len(
        url_mapping
    )

    print(
        "Unique URLs:",
        unique_url_count
    )

    # --------------------------------------------------------
    # 6. Convert URL mapping to Dask
    # --------------------------------------------------------

    print("\nCreating Dask URL mapping...")

    mapping_partitions = max(
        1,
        min(
            32,
            unique_url_count // 5000 + 1
        )
    )

    url_mapping_dd = dd.from_pandas(
        url_mapping,
        npartitions=mapping_partitions,
    )

    print(
        "URL mapping partitions:",
        mapping_partitions
    )

    # --------------------------------------------------------
    # 7. Map URL classes back to HTTP events
    # --------------------------------------------------------

    print(
        "\nMapping URL classes to HTTP events..."
    )

    events_with_class = events.merge(
        url_mapping_dd,
        on="url",
        how="left",
    )

    events_with_class = events_with_class[
        [
            "url",
            "event_id",
            "timestamp",
            "source",
            "event_type",
            "action",
            "resource",
            "raw_user_id",
            "device_id",
            "class_number",
            "class_label",
        ]
    ]

    events_with_class_count = (
        events_with_class
        .shape[0]
        .compute()
    )

    print(
        "HTTP events with URL classes:",
        events_with_class_count
    )

    # --------------------------------------------------------
    # 8. Verify event count
    # --------------------------------------------------------

    print("\nVerifying event counts...")

    if normalized_events != events_with_class_count:

        raise RuntimeError(
            "Event count mismatch detected. "
            f"Normalized={normalized_events}, "
            f"WithClasses={events_with_class_count}"
        )

    print(
        "Event count verification: PASSED"
    )

    # --------------------------------------------------------
    # 9. Display URL mapping sample
    # --------------------------------------------------------

    print("\nSample URL -> class mapping:")

    print(
        url_mapping
        .head(20)
        .to_string(index=False)
    )

    # --------------------------------------------------------
    # 10. Display processed HTTP sample
    # --------------------------------------------------------

    print("\nSample processed HTTP events:")

    print(
        events_with_class
        .head(10)
        .to_string(index=False)
    )

    # --------------------------------------------------------
    # 11. Prepare temporary output directories
    # --------------------------------------------------------

    print(
        "\nPreparing temporary output directories..."
    )

    temp_events = create_temp_output(
        OUTPUT_EVENTS
    )

    temp_urls = create_temp_output(
        OUTPUT_URLS
    )

    print(
        "Temporary HTTP output:",
        temp_events
    )

    print(
        "Temporary URL output:",
        temp_urls
    )

    # --------------------------------------------------------
    # 12. Write HTTP events
    # --------------------------------------------------------

    print(
        "\nWriting HTTP events to Parquet..."
    )

    events_with_class.to_parquet(
        temp_events,
        engine="pyarrow",
        compression="snappy",
        write_index=False,
    )

    print(
        "HTTP event Parquet write: COMPLETE"
    )

    # --------------------------------------------------------
    # 13. Write URL class mapping
    # --------------------------------------------------------

    print(
        "\nWriting URL class mapping to Parquet..."
    )

    url_mapping_dd.to_parquet(
        temp_urls,
        engine="pyarrow",
        compression="snappy",
        write_index=False,
    )

    print(
        "URL mapping Parquet write: COMPLETE"
    )

    # --------------------------------------------------------
    # 14. Replace final output directories
    # --------------------------------------------------------

    print(
        "\nFinalizing output directories..."
    )

    events_replaced = replace_output_directory(
        temp_events,
        OUTPUT_EVENTS
    )

    urls_replaced = replace_output_directory(
        temp_urls,
        OUTPUT_URLS
    )

    # --------------------------------------------------------
    # 15. Final verification
    # --------------------------------------------------------

    print("\n===================================")
    print("HTTP PROCESSING COMPLETE")
    print("===================================")

    print(
        "Raw HTTP events:",
        raw_events
    )

    print(
        "Normalized HTTP events:",
        normalized_events
    )

    print(
        "Unique URLs:",
        unique_url_count
    )

    print(
        "HTTP events with URL classes:",
        events_with_class_count
    )

    print(
        "Event count verification: PASSED"
    )

    print(
        "\nHTTP event output:",
        OUTPUT_EVENTS
    )

    print(
        "URL class mapping:",
        OUTPUT_URLS
    )

    print(
        "\nOutput finalization:"
    )

    print(
        "HTTP events finalized:",
        events_replaced
    )

    print(
        "URL mapping finalized:",
        urls_replaced
    )

    if not events_replaced or not urls_replaced:

        print(
            "\nWARNING:"
        )

        print(
            "Processing itself completed successfully,"
        )

        print(
            "but Windows/OneDrive prevented replacing "
            "one or more existing output directories."
        )

        print(
            "The newly generated temporary output "
            "directories are still available."
        )

    else:

        print(
            "\nAll HTTP processing outputs finalized successfully."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()