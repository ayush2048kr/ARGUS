import json
import os
import sys
import time
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq

# ============================================================
# CONFIGURATIONS & EXPORT SPECIFICATIONS
# ============================================================

OUTPUT_DIR = "data/processed/csv_exports"
SUMMARY_FILE = os.path.join(OUTPUT_DIR, "export_summary.txt")

EXPORT_CONFIGS = [
    {
        "name": "MASTER EVENT SAMPLE",
        "source_path": "data/processed/argus_all_events",
        "output_filename": "argus_all_events_sample.csv",
        "is_sample": True,
        "sample_size": 10000,
        "sort_cols": ["timestamp", "event_id"]
    },
    {
        "name": "HTTP EVENT SAMPLE",
        "source_path": "data/processed/http_events",
        "output_filename": "http_events_sample.csv",
        "is_sample": True,
        "sample_size": 10000,
        "sort_cols": ["timestamp", "event_id"]
    },
    {
        "name": "HTTP ENRICHED EVENT SAMPLE",
        "source_path": "data/processed/http_enriched_events",
        "output_filename": "http_enriched_events_sample.csv",
        "is_sample": True,
        "sample_size": 10000,
        "sort_cols": ["timestamp", "event_id"]
    },
    {
        "name": "URL CLASSIFICATION MAPPING",
        "source_path": "data/processed/url_class_mapping",
        "output_filename": "url_class_mapping.csv",
        "is_sample": False,
        "sample_size": None,
        "sort_cols": ["url"]
    },
    {
        "name": "STAGE 1 DAILY FEATURES",
        "source_path": "data/processed/user_features_stage1_daily.parquet",
        "output_filename": "user_features_stage1_daily.csv",
        "is_sample": False,
        "sample_size": None,
        "sort_cols": ["user_id", "date"]
    },
    {
        "name": "STAGE 2 HISTORICAL FEATURES",
        "source_path": "data/processed/user_features_stage2_history.parquet",
        "output_filename": "user_features_stage2_history.csv",
        "is_sample": False,
        "sample_size": None,
        "sort_cols": ["user_id", "date"]
    },
    {
        "name": "STAGE 3 PEER CLUSTERS",
        "source_path": "data/processed/user_peer_clusters.parquet",
        "output_filename": "user_peer_clusters.csv",
        "is_sample": False,
        "sample_size": None,
        "sort_cols": ["user_id"]
    }
]


def export_datasets_to_csv():
    print("============================================================")
    print("ARGUS DATASET CSV EXPORTER")
    print("============================================================")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    summary_lines = [
        "=" * 80,
        "ARGUS PROCESSED DATASETS CSV EXPORT SUMMARY",
        f"Generated At: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 80,
        f"{'Dataset Name':<30} | {'Type':<8} | {'Source Rows':>12} | {'Exported Rows':>14} | {'Cols':>5} | {'File Size':>12} | {'Output CSV File'}",
        "-" * 130
    ]

    export_results = []

    for cfg in EXPORT_CONFIGS:
        name = cfg["name"]
        source_path = cfg["source_path"]
        out_filename = cfg["output_filename"]
        out_path = os.path.join(OUTPUT_DIR, out_filename)
        is_sample = cfg["is_sample"]
        sample_size = cfg["sample_size"]
        sort_cols = cfg["sort_cols"]

        print(f"\n[Processing] {name}...")
        print(f"  Source: {source_path}")

        t0 = time.time()
        # Read dataset efficiently via pyarrow
        dataset = ds.dataset(source_path, format="parquet")
        source_cols = dataset.schema.names
        table = dataset.to_table()
        source_row_count = table.num_rows

        df = table.to_pandas()

        if is_sample:
            export_type = "SAMPLE"
            actual_sample_size = min(sample_size, source_row_count)
            # Deterministic reproducible sample
            sampled_df = df.sample(n=actual_sample_size, random_state=42)
            # Sort for clean inspection
            if sort_cols and all(col in sampled_df.columns for col in sort_cols):
                sampled_df = sampled_df.sort_values(sort_cols)
            final_df = sampled_df.reset_index(drop=True)
        else:
            export_type = "COMPLETE"
            if sort_cols and all(col in df.columns for col in sort_cols):
                df = df.sort_values(sort_cols)
            final_df = df.reset_index(drop=True)

        # Handle list columns (such as profile_vector in Stage 3)
        for col in final_df.columns:
            if final_df[col].dtype == object and len(final_df) > 0:
                first_val = final_df[col].iloc[0]
                if isinstance(first_val, (list, np.ndarray)):
                    final_df[col] = final_df[col].apply(lambda x: json.dumps(list(x)) if hasattr(x, '__iter__') else x)

        # Ensure exact column order matching source
        final_df = final_df[source_cols]

        # Write to CSV with UTF-8 encoding and standard formatting
        final_df.to_csv(out_path, index=False, encoding="utf-8")
        file_size_bytes = os.path.getsize(out_path)
        file_size_str = f"{file_size_bytes / (1024 * 1024):.2f} MB" if file_size_bytes >= 1024 * 1024 else f"{file_size_bytes / 1024:.1f} KB"

        elapsed = time.time() - t0
        print(f"  -> Exported {len(final_df):,d} rows to {out_path} ({file_size_str}) in {elapsed:.2f}s")

        summary_lines.append(
            f"{name:<30} | {export_type:<8} | {source_row_count:>12,d} | {len(final_df):>14,d} | {len(source_cols):>5d} | {file_size_str:>12} | {out_filename}"
        )

        export_results.append({
            "name": name,
            "source_path": source_path,
            "output_path": out_path,
            "output_filename": out_filename,
            "source_rows": source_row_count,
            "exported_rows": len(final_df),
            "column_count": len(source_cols),
            "column_names": source_cols,
            "file_size_bytes": file_size_bytes,
            "file_size_str": file_size_str,
            "export_type": export_type,
            "first_5": final_df.head(5),
            "last_5": final_df.tail(5),
            "null_counts": final_df.isnull().sum().to_dict()
        })

    summary_lines.extend([
        "-" * 130,
        "All CSV exports completed successfully. Original Parquet datasets remain untouched.",
        "=" * 80
    ])

    summary_text = "\n".join(summary_lines)
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(summary_text)

    print("\n" + summary_text)
    print(f"\n[Summary Saved] {SUMMARY_FILE}")
    return export_results


if __name__ == "__main__":
    export_datasets_to_csv()
