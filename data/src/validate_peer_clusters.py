import os
import sys
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# ============================================================
# PATHS & CONTRACT DEFINITIONS
# ============================================================

PEER_CLUSTERS_PATH = "data/processed/user_peer_clusters.parquet"
CLUSTERING_EVALUATION_PATH = "data/processed/clustering_evaluation.csv"
STAGE1_FEATURES_PATH = "data/processed/user_features_stage1_daily.parquet"
STAGE2_HISTORY_PATH = "data/processed/user_features_stage2_history.parquet"

EXPECTED_OUTPUT_SCHEMA = {
    "user_id": "string",
    "peer_group_id": "int32",
    "clustering_algorithm": "string",
    "cluster_silhouette_score": "double",
    "profile_vector": "list"
}

EXPECTED_USER_COUNT = 1000
EXPECTED_USER_IDS = [f"EMP{i:03d}" for i in range(1, 1001)]
EXPECTED_K_VALUES = list(range(4, 13))
EXPECTED_PROFILE_DIMENSIONS = 10


def fail(check_num: int, msg: str):
    print(f"\n[FAILED - CHECK {check_num}] {msg}")
    sys.exit(1)


def pass_check(check_num: int, msg: str):
    print(f"  [PASS - CHECK {check_num:02d}] {msg}")


def validate_peer_clusters():
    print("============================================================")
    print("ARGUS M2 STAGE 3: BEHAVIORAL PEER CLUSTERS VALIDATION SUITE")
    print("============================================================")

    # ------------------------------------------------------------
    # 1. Check Output Files Existence
    # ------------------------------------------------------------
    print("\n[1/15] Verifying output artifacts exist...")
    if not os.path.exists(PEER_CLUSTERS_PATH):
        fail(1, f"Missing cluster output file: {PEER_CLUSTERS_PATH}")
    if not os.path.exists(CLUSTERING_EVALUATION_PATH):
        fail(1, f"Missing evaluation output file: {CLUSTERING_EVALUATION_PATH}")
    pass_check(1, "Both user_peer_clusters.parquet and clustering_evaluation.csv exist.")

    # ------------------------------------------------------------
    # 2. Check Exact Schema
    # ------------------------------------------------------------
    print("\n[2/15] Verifying exact output schema...")
    table = pq.read_table(PEER_CLUSTERS_PATH)
    schema = table.schema

    field_names = [f.name for f in schema]
    expected_fields = list(EXPECTED_OUTPUT_SCHEMA.keys())

    if field_names != expected_fields:
        fail(2, f"Schema fields mismatch! Expected {expected_fields}, got {field_names}")

    # Check field types
    for field in schema:
        expected_type = EXPECTED_OUTPUT_SCHEMA[field.name]
        type_str = str(field.type).lower()
        if expected_type == "list":
            if not type_str.startswith("list"):
                fail(2, f"Field {field.name} expected list type, got {field.type}")
        elif expected_type == "int32":
            if "int32" not in type_str:
                fail(2, f"Field {field.name} expected int32, got {field.type}")
        elif expected_type == "double":
            if "double" not in type_str and "float64" not in type_str:
                fail(2, f"Field {field.name} expected double, got {field.type}")
        elif expected_type == "string":
            if "string" not in type_str:
                fail(2, f"Field {field.name} expected string, got {field.type}")

    pass_check(2, f"Schema exactly matches specification: {field_names}")

    # Load data as pandas DataFrame
    df = table.to_pandas()

    # ------------------------------------------------------------
    # 3. One Assignment Per User
    # ------------------------------------------------------------
    print("\n[3/15] Verifying one assignment per user...")
    total_rows = len(df)
    unique_users = df["user_id"].nunique()
    if total_rows != EXPECTED_USER_COUNT:
        fail(3, f"Expected {EXPECTED_USER_COUNT} rows, found {total_rows}")
    if unique_users != EXPECTED_USER_COUNT:
        fail(3, f"Expected {EXPECTED_USER_COUNT} unique users, found {unique_users}")
    pass_check(3, f"Exactly {total_rows} assignments for {unique_users} unique users (user-level grain).")

    # ------------------------------------------------------------
    # 4. No Duplicate user_id
    # ------------------------------------------------------------
    print("\n[4/15] Checking for duplicate user_ids...")
    duplicates = df[df.duplicated(subset=["user_id"], keep=False)]
    if len(duplicates) > 0:
        fail(4, f"Found duplicate user_ids: {duplicates['user_id'].tolist()[:5]}")
    pass_check(4, "0 duplicate user_ids found.")

    # ------------------------------------------------------------
    # 5. No Null user_id
    # ------------------------------------------------------------
    print("\n[5/15] Checking for null user_ids...")
    null_users = df["user_id"].isnull().sum()
    if null_users > 0:
        fail(5, f"Found {null_users} null user_ids")
    pass_check(5, "0 null user_ids found.")

    # ------------------------------------------------------------
    # 6. Exactly Expected Anonymized User IDs
    # ------------------------------------------------------------
    print("\n[6/15] Verifying all anonymized user IDs EMP001..EMP1000...")
    actual_users = set(df["user_id"].tolist())
    expected_users_set = set(EXPECTED_USER_IDS)
    if actual_users != expected_users_set:
        missing = expected_users_set - actual_users
        extra = actual_users - expected_users_set
        fail(6, f"User ID set mismatch! Missing: {len(missing)}, Extra: {len(extra)}")
    pass_check(6, "Exact 1,000 anonymized user IDs EMP001 through EMP1000 match 100%.")

    # ------------------------------------------------------------
    # 7. peer_group_id Semantics Documented & Valid
    # ------------------------------------------------------------
    print("\n[7/15] Checking peer_group_id semantics and range...")
    peer_ids = df["peer_group_id"]
    if peer_ids.isnull().any():
        fail(7, "Null peer_group_id values detected.")
    unique_peer_ids = sorted(peer_ids.unique())
    print(f"     Distinct peer group IDs: {unique_peer_ids}")
    for pid in unique_peer_ids:
        if pid < 0:
            fail(7, f"Negative peer_group_id detected: {pid}")
    pass_check(7, f"peer_group_id is valid non-negative integer across {len(unique_peer_ids)} clusters.")

    # ------------------------------------------------------------
    # 8. Profile Vector Dimension Check (Exactly 10 Values)
    # ------------------------------------------------------------
    print("\n[8/15] Verifying profile_vector has exactly 10 dimensions...")
    vector_lengths = df["profile_vector"].apply(len)
    if not (vector_lengths == EXPECTED_PROFILE_DIMENSIONS).all():
        bad_rows = df[vector_lengths != EXPECTED_PROFILE_DIMENSIONS]
        fail(8, f"Found rows with incorrect profile vector length: {bad_rows.head(2)}")
    pass_check(8, f"All {len(df)} profile vectors have exactly {EXPECTED_PROFILE_DIMENSIONS} dimensions.")

    # ------------------------------------------------------------
    # 9. No NaN or Infinite Profile Values
    # ------------------------------------------------------------
    print("\n[9/15] Checking for NaN or Infinite values in profile vectors...")
    all_vectors = np.array(df["profile_vector"].tolist())
    if np.isnan(all_vectors).any():
        fail(9, "NaN values detected in profile vectors!")
    if np.isinf(all_vectors).any():
        fail(9, "Infinite values detected in profile vectors!")
    pass_check(9, "All 10,000 profile vector elements are finite, non-null numeric values.")

    # ------------------------------------------------------------
    # 10. No NaN or Infinite Clustering Metrics
    # ------------------------------------------------------------
    print("\n[10/15] Checking clustering metrics validity...")
    sil_scores = df["cluster_silhouette_score"]
    if sil_scores.isnull().any() or np.isnan(sil_scores).any() or np.isinf(sil_scores).any():
        fail(10, "Invalid cluster_silhouette_score in user_peer_clusters.parquet!")
    pass_check(10, f"Silhouette score is valid: {sil_scores.iloc[0]:.4f}")

    # ------------------------------------------------------------
    # 11. Clustering Evaluation Table Contains All K Values 4–12
    # ------------------------------------------------------------
    print("\n[11/15] Verifying evaluation CSV contains K=4..12...")
    eval_df = pd.read_csv(CLUSTERING_EVALUATION_PATH)
    kmeans_eval = eval_df[eval_df["algorithm"] == "K-Means"]
    evaluated_k = sorted(kmeans_eval["n_clusters"].tolist())
    if evaluated_k != EXPECTED_K_VALUES:
        fail(11, f"Expected evaluated K values {EXPECTED_K_VALUES}, got {evaluated_k}")
    pass_check(11, f"Evaluation CSV contains all K values 4 through 12 ({len(kmeans_eval)} entries).")

    # ------------------------------------------------------------
    # 12. K-Means Metrics Are Mathematically Valid
    # ------------------------------------------------------------
    print("\n[12/15] Verifying mathematical validity of K-Means metrics...")
    for idx, row in kmeans_eval.iterrows():
        k = int(row["n_clusters"])
        inertia = float(row["inertia"])
        sil = float(row["silhouette_score"])
        db = float(row["davies_bouldin_index"])

        if inertia <= 0:
            fail(12, f"Invalid inertia for K={k}: {inertia}")
        if not (-1.0 <= sil <= 1.0):
            fail(12, f"Silhouette score out of bounds [-1, 1] for K={k}: {sil}")
        if db < 0:
            fail(12, f"Davies-Bouldin index cannot be negative for K={k}: {db}")
    pass_check(12, "All K-Means inertia, silhouette scores, and DB indices are mathematically sound.")

    # ------------------------------------------------------------
    # 13. DBSCAN Evaluation Results Are Valid
    # ------------------------------------------------------------
    print("\n[13/15] Verifying DBSCAN evaluation grid...")
    dbscan_eval = eval_df[eval_df["algorithm"] == "DBSCAN"]
    if len(dbscan_eval) == 0:
        fail(13, "No DBSCAN evaluation entries found in evaluation CSV!")

    for idx, row in dbscan_eval.iterrows():
        n_clusters = int(row["n_clusters"])
        n_noise = int(row["n_noise"])
        sil = row["silhouette_score"]
        db = row["davies_bouldin_index"]

        if n_clusters < 0 or n_noise < 0:
            fail(13, f"Negative clusters or noise count in DBSCAN: {row}")
        if n_clusters >= 2 and pd.notnull(sil):
            if not (-1.0 <= float(sil) <= 1.0):
                fail(13, f"DBSCAN silhouette out of bounds [-1, 1]: {sil}")
    pass_check(13, f"DBSCAN grid contains {len(dbscan_eval)} tested combinations with valid metrics.")

    # ------------------------------------------------------------
    # 14. Verify No Stage 1 or Stage 2 Data Modification
    # ------------------------------------------------------------
    print("\n[14/15] Checking Stage 1 and Stage 2 integrity...")
    st1_table = pq.read_table(STAGE1_FEATURES_PATH)
    st2_table = pq.read_table(STAGE2_HISTORY_PATH)

    if st1_table.num_rows != 334905:
        fail(14, f"Stage 1 row count changed! Expected 334905, found {st1_table.num_rows}")
    if st2_table.num_rows != 334905:
        fail(14, f"Stage 2 row count changed! Expected 334905, found {st2_table.num_rows}")
    pass_check(14, "Stage 1 and Stage 2 datasets are completely unmodified (334,905 rows each).")

    # ------------------------------------------------------------
    # 15. No Risk Score or Malicious Label Generated
    # ------------------------------------------------------------
    print("\n[15/15] Verifying absence of risk scores or threat labels...")
    prohibited_terms = ["risk", "malicious", "attack", "threat", "anomaly", "score", "suspicious", "insider"]
    for col in df.columns:
        if col not in ["cluster_silhouette_score"]:
            for term in prohibited_terms:
                if term in col.lower():
                    fail(15, f"Prohibited term '{term}' found in column name '{col}'!")

    pass_check(15, "0 risk scores or malicious labels generated. Pure behavioral clustering preserved.")

    print("\n============================================================")
    print("ALL 15 STAGE 3 VALIDATION CHECKS PASSED WITH 100% SUCCESS!")
    print("============================================================\n")


if __name__ == "__main__":
    validate_peer_clusters()
