import os
import glob
import csv
import pyarrow.parquet as pq


INPUT_PATH = r"C:\Users\ayush\OneDrive\Desktop\ARGUS\data\processed\url_class_mapping"

OUTPUT_FILE = r"C:\Users\ayush\OneDrive\Desktop\ARGUS\data\processed\url_class_mapping.csv"


def main():

    print("===================================")
    print("URL CLASS MAPPING -> CSV")
    print("===================================")

    # Find all parquet files
    parquet_files = sorted(
        glob.glob(os.path.join(INPUT_PATH, "*.parquet"))
    )

    if not parquet_files:
        raise FileNotFoundError(
            f"No Parquet files found in: {INPUT_PATH}"
        )

    print(f"\nFound {len(parquet_files)} Parquet files.")

    total_rows = 0
    first_file = True

    temp_file = OUTPUT_FILE + ".tmp"

    try:
        with open(
            temp_file,
            "w",
            newline="",
            encoding="utf-8"
        ) as csv_file:

            writer = None

            for index, parquet_file in enumerate(parquet_files, start=1):

                print(
                    f"Reading {index}/{len(parquet_files)}: "
                    f"{os.path.basename(parquet_file)}"
                )

                table = pq.read_table(parquet_file)

                rows = table.to_pylist()

                if not rows:
                    continue

                # Create CSV writer using columns from first file
                if writer is None:
                    columns = table.column_names

                    writer = csv.DictWriter(
                        csv_file,
                        fieldnames=columns
                    )

                    writer.writeheader()

                writer.writerows(rows)

                total_rows += len(rows)

        # Safely move temp file to output file
        if os.path.exists(OUTPUT_FILE):
            try:
                os.replace(temp_file, OUTPUT_FILE)
            except OSError as e:
                print(f"\nWARNING: Could not replace {OUTPUT_FILE} (file locked): {e}")
                print(f"Aggregated CSV available at: {temp_file}")
                return
        else:
            os.rename(temp_file, OUTPUT_FILE)

    except Exception as e:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise e

    print("\n===================================")
    print("CONVERSION COMPLETE")
    print("===================================")

    print(f"Parquet files processed: {len(parquet_files)}")
    print(f"Total rows: {total_rows}")
    print(f"CSV created at:")
    print(OUTPUT_FILE)

    print("===================================")


if __name__ == "__main__":
    main()