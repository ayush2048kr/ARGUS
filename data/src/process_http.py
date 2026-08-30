import os
import shutil

import dask.dataframe as dd
import pandas as pd


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


def remove_output(path):
    """Safely remove an existing output directory."""
    if os.path.exists(path):
        print(f"Removing existing output: {path}")
        shutil.rmtree(path)


def main():

    print("===================================")
    print("ARGUS HTTP PROCESSING - DASK")
    print("===================================")

    # ---------------------------------------------------------
    # 1. Read raw HTTP data
    # ---------------------------------------------------------

    print("\nReading HTTP data with Dask...")

    http = dd.read_csv(
        INPUT_PATH,
        header=None,
        names=RAW_COLUMNS,
        dtype="string",
        blocksize="64MB",
    )

    raw_events = http.shape[0].compute()

    print("Raw HTTP events:", raw_events)

    # ---------------------------------------------------------
    # 2. Normalize HTTP events
    # ---------------------------------------------------------

    print("\nNormalizing HTTP events...")

    http["timestamp"] = dd.to_datetime(
        http["raw_timestamp"],
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce",
    )

    http["event_id"] = (
        "ARG-HTTP-" + http["raw_event_id"].astype("string")
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

    normalized_events = events.shape[0].compute()

    print("Normalized HTTP events:", normalized_events)

    # ---------------------------------------------------------
    # 3. Clean URLs
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # 4. Extract unique URLs
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # 5. Create deterministic URL classes
    # ---------------------------------------------------------

    unique_urls_df["class_number"] = (
        unique_urls_df.index
    )

    unique_urls_df["class_label"] = (
        "class_"
        + unique_urls_df["class_number"].astype(str)
    )

    url_mapping = unique_urls_df[
        [
            "url",
            "class_number",
            "class_label",
        ]
    ]

    unique_url_count = len(url_mapping)

    print("Unique URLs:", unique_url_count)

    # ---------------------------------------------------------
    # 6. Convert mapping to Dask DataFrame
    # ---------------------------------------------------------

    print("\nCreating Dask URL mapping...")

    url_mapping_dd = dd.from_pandas(
        url_mapping,
        npartitions=max(
            1,
            min(
                32,
                len(url_mapping) // 5000 + 1
            )
        ),
    )

    # ---------------------------------------------------------
    # 7. Map URL classes back to HTTP events
    # ---------------------------------------------------------

    print("\nMapping URL classes to HTTP events...")

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
        events_with_class.shape[0].compute()
    )

    print(
        "HTTP events with URL classes:",
        events_with_class_count,
    )

    # ---------------------------------------------------------
    # 8. Display URL mapping sample
    # ---------------------------------------------------------

    print("\nSample URL -> class mapping:")

    print(
        url_mapping
        .head(20)
        .to_string(index=False)
    )

    # ---------------------------------------------------------
    # 9. Display processed HTTP sample
    # ---------------------------------------------------------

    print("\nSample processed HTTP events:")

    print(
        events_with_class
        .head(10)
        .to_string(index=False)
    )

    # ---------------------------------------------------------
    # 10. Remove old outputs
    # ---------------------------------------------------------

    print("\nPreparing output directories...")

    remove_output(OUTPUT_EVENTS)
    remove_output(OUTPUT_URLS)

    # ---------------------------------------------------------
    # 11. Write HTTP events
    # ---------------------------------------------------------

    print("\nWriting HTTP events to Parquet...")

    events_with_class.to_parquet(
        OUTPUT_EVENTS,
        engine="pyarrow",
        compression="snappy",
        write_index=False,
    )

    # ---------------------------------------------------------
    # 12. Write URL class mapping
    # ---------------------------------------------------------

    print("Writing URL class mapping to Parquet...")

    url_mapping_dd.to_parquet(
        OUTPUT_URLS,
        engine="pyarrow",
        compression="snappy",
        write_index=False,
    )

    # ---------------------------------------------------------
    # 13. Final verification
    # ---------------------------------------------------------

    print("\n===================================")
    print("HTTP PROCESSING COMPLETE")
    print("===================================")

    print("HTTP events:", normalized_events)
    print("Unique URLs:", unique_url_count)
    print(
        "HTTP events with URL classes:",
        events_with_class_count,
    )

    print(
        "HTTP event output:",
        OUTPUT_EVENTS,
    )

    print(
        "URL class mapping:",
        OUTPUT_URLS,
    )


if __name__ == "__main__":
    main()