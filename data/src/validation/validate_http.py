import os
import sys

import dask.dataframe as dd


# =========================================================
# ARGUS HTTP EVENT VALIDATION
# =========================================================

INPUT_PATH = "data/processed/http_events"

REQUIRED_COLUMNS = [
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


def fail(message):
    """Print an error and stop validation."""
    print("\nVALIDATION FAILED")
    print("-----------------------------------")
    print(message)
    sys.exit(1)


def main():
    print("===================================")
    print("ARGUS HTTP EVENT VALIDATION")
    print("===================================")

    # -----------------------------------------------------
    # 1. Check input path
    # -----------------------------------------------------

    print("\nChecking HTTP event output...")

    if not os.path.exists(INPUT_PATH):
        fail(
            f"HTTP event output does not exist:\n"
            f"{INPUT_PATH}"
        )

    print("HTTP event output found:", INPUT_PATH)

    # -----------------------------------------------------
    # 2. Read Parquet
    # -----------------------------------------------------

    print("\nReading HTTP events with Dask...")

    try:
        events = dd.read_parquet(
            INPUT_PATH,
            engine="pyarrow",
        )
    except Exception as exc:
        fail(
            f"Unable to read HTTP Parquet output:\n{exc}"
        )

    print("Parquet read: PASSED")

    # -----------------------------------------------------
    # 3. Check columns
    # -----------------------------------------------------

    print("\nChecking required columns...")

    actual_columns = events.columns.tolist()

    print("Columns found:")
    for column in actual_columns:
        print(" -", column)

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in actual_columns
    ]

    if missing_columns:
        fail(
            "Missing required columns:\n"
            + "\n".join(
                f" - {column}"
                for column in missing_columns
            )
        )

    print("Required columns: PASSED")

    # -----------------------------------------------------
    # 4. Count events
    # -----------------------------------------------------

    print("\nCounting HTTP events...")

    event_count = events.shape[0].compute()

    print("HTTP events:", event_count)

    if event_count == 0:
        fail("HTTP event output contains zero rows.")

    print("Event count: PASSED")

    # -----------------------------------------------------
    # 5. Check null values
    # -----------------------------------------------------

    print("\nChecking required fields for null values...")

    required_non_null = [
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

    null_counts = {}

    for column in required_non_null:
        count = events[column].isnull().sum().compute()

        null_counts[column] = int(count)

        print(
            f"{column}: {count} null values"
        )

        if count > 0:
            fail(
                f"Column '{column}' contains "
                f"{count} null values."
            )

    print("Required field null check: PASSED")

    # -----------------------------------------------------
    # 6. Check empty URLs
    # -----------------------------------------------------

    print("\nChecking empty URLs...")

    empty_urls = (
        events["url"]
        .astype("string")
        .str.strip()
        .eq("")
        .sum()
        .compute()
    )

    print("Empty URLs:", empty_urls)

    if empty_urls > 0:
        fail(
            f"Found {empty_urls} empty URL values."
        )

    print("URL validation: PASSED")

    # -----------------------------------------------------
    # 7. Check event IDs
    # -----------------------------------------------------

    print("\nChecking event IDs...")

    invalid_event_ids = (
        ~events["event_id"]
        .astype("string")
        .str.startswith("ARG-HTTP-")
    ).sum().compute()

    print(
        "Invalid ARGUS HTTP event IDs:",
        invalid_event_ids,
    )

    if invalid_event_ids > 0:
        fail(
            f"Found {invalid_event_ids} event IDs "
            f"that do not start with 'ARG-HTTP-'."
        )

    print("Event ID validation: PASSED")

    # -----------------------------------------------------
    # 8. Check source
    # -----------------------------------------------------

    print("\nChecking event source...")

    invalid_sources = (
        events["source"] != "HTTP"
    ).sum().compute()

    print("Non-HTTP source values:", invalid_sources)

    if invalid_sources > 0:
        fail(
            f"Found {invalid_sources} events "
            f"with an invalid source."
        )

    print("Source validation: PASSED")

    # -----------------------------------------------------
    # 9. Check event type
    # -----------------------------------------------------

    print("\nChecking event type...")

    invalid_event_types = (
        events["event_type"] != "HTTP_ACTIVITY"
    ).sum().compute()

    print(
        "Invalid event types:",
        invalid_event_types,
    )

    if invalid_event_types > 0:
        fail(
            f"Found {invalid_event_types} events "
            f"with an invalid event_type."
        )

    print("Event type validation: PASSED")

    # -----------------------------------------------------
    # 10. Check action
    # -----------------------------------------------------

    print("\nChecking action...")

    invalid_actions = (
        events["action"] != "VISIT_URL"
    ).sum().compute()

    print("Invalid actions:", invalid_actions)

    if invalid_actions > 0:
        fail(
            f"Found {invalid_actions} events "
            f"with an invalid action."
        )

    print("Action validation: PASSED")

    # -----------------------------------------------------
    # 11. Check URL classes
    # -----------------------------------------------------

    print("\nChecking URL class assignments...")

    invalid_class_numbers = (
        events["class_number"] < 0
    ).sum().compute()

    print(
        "Invalid class numbers:",
        invalid_class_numbers,
    )

    if invalid_class_numbers > 0:
        fail(
            "Found URL classes with negative "
            "class numbers."
        )

    # Check that class label matches class number.
    expected_labels = (
        "class_"
        + events["class_number"]
        .astype("string")
    )

    invalid_class_labels = (
        events["class_label"] != expected_labels
    ).sum().compute()

    print(
        "Invalid class labels:",
        invalid_class_labels,
    )

    if invalid_class_labels > 0:
        fail(
            "Found class labels that do not match "
            "their class numbers."
        )

    print("URL class validation: PASSED")

    # -----------------------------------------------------
    # 12. Check duplicate event IDs
    # -----------------------------------------------------

    print("\nChecking duplicate event IDs...")

    duplicate_event_ids = (
        event_count
        - events["event_id"]
        .nunique()
        .compute()
    )

    print(
        "Duplicate event IDs:",
        duplicate_event_ids,
    )

    if duplicate_event_ids > 0:
        fail(
            f"Found {duplicate_event_ids} "
            "duplicate event IDs."
        )

    print("Event ID uniqueness: PASSED")

    # -----------------------------------------------------
    # 13. Display sample
    # -----------------------------------------------------

    print("\nSample validated HTTP events:")

    sample = events.head(5)

    print(
        sample.to_string(index=False)
    )

    # -----------------------------------------------------
    # 14. Final result
    # -----------------------------------------------------

    print("\n===================================")
    print("HTTP VALIDATION COMPLETE")
    print("===================================")

    print("Validation status: PASSED")
    print("HTTP events:", event_count)
    print("Required columns:", len(REQUIRED_COLUMNS))
    print("Duplicate event IDs:", duplicate_event_ids)

    print("\nHTTP processed data is valid and ready")
    print("for the next ARGUS data/ML pipeline stage.")


if __name__ == "__main__":
    main()