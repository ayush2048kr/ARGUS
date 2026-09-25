import json
import os
import shutil
import uuid
from urllib.parse import urlparse

import dask.dataframe as dd
import pandas as pd


# ============================================================
# ARGUS HTTP DATA PROCESSING & SEMANTIC URL CLASSIFICATION
# ============================================================

INPUT_PATH = "data/raw/http.csv"
CATEGORIES_PATH = "data/schema/url_categories.json"

OUTPUT_EVENTS = "data/processed/http_events"
OUTPUT_URLS = "data/processed/url_class_mapping"

RAW_COLUMNS = [
    "raw_event_id",
    "raw_timestamp",
    "raw_user_id",
    "device_id",
    "url",
]

CONTROLLED_TAXONOMY = [
    "social_media",
    "email",
    "search",
    "news",
    "shopping",
    "finance",
    "cloud_storage",
    "file_sharing",
    "video_entertainment",
    "music_entertainment",
    "technology",
    "productivity",
    "education",
    "travel",
    "security",
    "government",
    "other",
    "unknown",
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
    """
    if os.path.exists(final_path):
        backup_path = (
            final_path
            + "_old_"
            + uuid.uuid4().hex[:8]
        )
        print(f"Existing output found: {final_path}")
        print(f"Temporarily moving existing output to: {backup_path}")

        try:
            os.rename(final_path, backup_path)
        except PermissionError:
            print("\nWARNING: Existing output directory is locked.")
            print("Please close programs using the folder.")
            print(f"\nNew output remains available at:\n{temp_path}")
            return False
        except OSError as error:
            print(f"\nWARNING: Could not move existing output directory: {error}")
            print(f"\nNew output remains available at:\n{temp_path}")
            return False

    try:
        os.rename(temp_path, final_path)
        print(f"Output successfully written to: {final_path}")
        return True
    except OSError as error:
        print(f"\nWARNING: Could not rename temporary output: {error}")
        print(f"\nTemporary output remains at:\n{temp_path}")
        return False


def load_url_categories(config_path=CATEGORIES_PATH):
    """
    Load domain-to-category mapping from JSON configuration.
    """
    if not os.path.exists(config_path):
        print(f"WARNING: Categories config not found at {config_path}. Falling back to empty mapping.")
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

    # 2. Check parent domains (e.g., sub.facebook.com -> facebook.com)
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

    # 4. Fallback for unclassified/synthetic domains
    return "unknown"


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
    # 5. Create deterministic URL classes and semantic categories
    # --------------------------------------------------------

    print("\nCreating deterministic URL classes & semantic categories...")

    domain_mapping = load_url_categories(CATEGORIES_PATH)
    print(f"Loaded {len(domain_mapping)} domain mappings from {CATEGORIES_PATH}")

    unique_urls_df["class_number"] = unique_urls_df.index
    unique_urls_df["class_label"] = (
        "class_"
        + unique_urls_df["class_number"].astype(str)
    )

    # Apply deterministic domain-based semantic classification
    unique_urls_df["url_category"] = unique_urls_df["url"].apply(
        lambda u: classify_url(u, domain_mapping)
    )

    # Verify all categories belong to controlled taxonomy
    invalid_cats = set(unique_urls_df["url_category"]) - set(CONTROLLED_TAXONOMY)
    if invalid_cats:
        raise ValueError(f"Invalid categories detected: {invalid_cats}")

    url_mapping = unique_urls_df[
        [
            "url",
            "class_number",
            "class_label",
            "url_category",
        ]
    ]

    unique_url_count = len(url_mapping)

    print("Unique URLs:", unique_url_count)

    # --------------------------------------------------------
    # Category Distribution Summary
    # --------------------------------------------------------

    print("\n===================================")
    print("URL CATEGORY DISTRIBUTION")
    print("===================================")

    category_counts = url_mapping["url_category"].value_counts()
    for cat in CONTROLLED_TAXONOMY:
        count = category_counts.get(cat, 0)
        pct = (count / unique_url_count) * 100
        print(f"  {cat:<22}: {count:>8} ({pct:>6.2f}%)")

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
    # 7. Map URL classes and categories back to HTTP events
    # --------------------------------------------------------

    print(
        "\nMapping URL classes and categories to HTTP events..."
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
            "url_category",
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

    print("Event count verification: PASSED")

    # --------------------------------------------------------
    # 9. Display URL mapping sample
    # --------------------------------------------------------

    print("\nSample URL -> category mapping:")
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

    print("\nPreparing temporary output directories...")

    temp_events = create_temp_output(OUTPUT_EVENTS)
    temp_urls = create_temp_output(OUTPUT_URLS)

    print("Temporary HTTP output:", temp_events)
    print("Temporary URL output:", temp_urls)

    # --------------------------------------------------------
    # 12. Write HTTP events
    # --------------------------------------------------------

    print("\nWriting HTTP events to Parquet...")

    events_with_class.to_parquet(
        temp_events,
        engine="pyarrow",
        compression="snappy",
        write_index=False,
    )

    print("HTTP event Parquet write: COMPLETE")

    # --------------------------------------------------------
    # 13. Write URL class mapping
    # --------------------------------------------------------

    print("\nWriting URL class mapping to Parquet...")

    url_mapping_dd.to_parquet(
        temp_urls,
        engine="pyarrow",
        compression="snappy",
        write_index=False,
    )

    print("URL mapping Parquet write: COMPLETE")

    # --------------------------------------------------------
    # 14. Replace final output directories
    # --------------------------------------------------------

    print("\nFinalizing output directories...")

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

    print("Raw HTTP events:", raw_events)
    print("Normalized HTTP events:", normalized_events)
    print("Unique URLs:", unique_url_count)
    print("HTTP events with URL classes & categories:", events_with_class_count)
    print("Event count verification: PASSED")

    print("\nHTTP event output:", OUTPUT_EVENTS)
    print("URL class mapping:", OUTPUT_URLS)

    print("\nOutput finalization:")
    print("HTTP events finalized:", events_replaced)
    print("URL mapping finalized:", urls_replaced)

    if not events_replaced or not urls_replaced:
        print("\nWARNING: Output directory swap was partially blocked by OneDrive/OS.")
        print("Newly generated temporary outputs remain available.")
    else:
        print("\nAll HTTP processing outputs finalized successfully.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()