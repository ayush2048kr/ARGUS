import datetime
import os
import sys
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# ============================================================
# PATH & CONFIGURATION CONSTANTS
# ============================================================

INPUT_STAGE1_FEATURES = "data/processed/user_features_stage1_daily.parquet"
OUTPUT_PEER_CLUSTERS = "data/processed/user_peer_clusters.parquet"
OUTPUT_EVALUATION_CSV = "data/processed/clustering_evaluation.csv"

# Temporal Train/Test Split Boundary (Option B: Formal Research Baseline)
# Prevents future temporal leakage into behavioral baseline peer groups.
TRAIN_START_DATE = datetime.date(2010, 1, 4)
TRAIN_END_DATE = datetime.date(2010, 6, 30)

PROFILE_FEATURE_COLUMNS = [
    "profile_mean_daily_logins",
    "profile_mean_daily_http",
    "profile_mean_daily_usb",
    "profile_off_hours_ratio",
    "profile_active_span_hours",
    "profile_tech_web_ratio",
    "profile_social_web_ratio",
    "profile_exfiltration_web_ratio",
    "profile_distinct_domains_mean",
    "profile_distinct_devices_mean"
]

RANDOM_SEED = 42


# ============================================================
# NUMERICAL SCALING & DISTANCE UTILITIES
# ============================================================

class NumpyStandardScaler:
    """Standardizes features by removing the mean and scaling to unit variance."""
    def __init__(self):
        self.mean_ = None
        self.scale_ = None

    def fit(self, X: np.ndarray) -> "NumpyStandardScaler":
        self.mean_ = np.mean(X, axis=0)
        self.scale_ = np.std(X, axis=0)
        # Avoid division by zero for constant features
        self.scale_[self.scale_ == 0.0] = 1.0
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean_) / self.scale_

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)


def euclidean_dist_matrix(A: np.ndarray, B: np.ndarray = None) -> np.ndarray:
    """Computes pairwise Euclidean distance matrix between matrix A and B."""
    if B is None:
        B = A
    dot_prods = np.dot(A, B.T)
    sq_a = np.sum(A ** 2, axis=1)[:, None]
    sq_b = np.sum(B ** 2, axis=1)[None, :]
    sq_dists = np.maximum(0.0, sq_a + sq_b - 2 * dot_prods)
    return np.sqrt(sq_dists)


# ============================================================
# CLUSTERING EVALUATION METRICS
# ============================================================

def compute_silhouette_score(X: np.ndarray, labels: np.ndarray) -> float:
    """
    Calculates the Silhouette Score across all valid (non-noise) clustered samples.
    Formula: s(i) = (b(i) - a(i)) / max(a(i), b(i))
    """
    unique_labels = np.unique(labels)
    unique_labels = unique_labels[unique_labels != -1]
    if len(unique_labels) < 2:
        return np.nan

    valid_mask = (labels != -1)
    if np.sum(valid_mask) < 2:
        return np.nan

    X_valid = X[valid_mask]
    labels_valid = labels[valid_mask]
    n_valid = len(labels_valid)

    dist_mat = euclidean_dist_matrix(X_valid)

    a = np.zeros(n_valid)
    b = np.full(n_valid, np.inf)

    for cluster in unique_labels:
        cluster_mask = (labels_valid == cluster)
        cluster_size = np.sum(cluster_mask)

        if cluster_size > 1:
            a[cluster_mask] = np.sum(dist_mat[cluster_mask][:, cluster_mask], axis=1) / (cluster_size - 1)
        else:
            a[cluster_mask] = 0.0

        for other_cluster in unique_labels:
            if other_cluster == cluster:
                continue
            other_mask = (labels_valid == other_cluster)
            other_size = np.sum(other_mask)
            if other_size > 0:
                mean_dist_to_other = np.mean(dist_mat[cluster_mask][:, other_mask], axis=1)
                b[cluster_mask] = np.minimum(b[cluster_mask], mean_dist_to_other)

    max_ab = np.maximum(a, b)
    s = np.where(max_ab == 0, 0, (b - a) / max_ab)
    return float(np.mean(s))


def compute_davies_bouldin_index(X: np.ndarray, labels: np.ndarray) -> float:
    """
    Calculates the Davies-Bouldin Index across valid (non-noise) clusters.
    Formula: DB = (1/k) * sum(max_{j != i} (s_i + s_j) / d(c_i, c_j))
    """
    unique_labels = np.unique(labels)
    unique_labels = unique_labels[unique_labels != -1]
    k = len(unique_labels)
    if k < 2:
        return np.nan

    centroids = np.zeros((k, X.shape[1]))
    s = np.zeros(k)

    for i, label in enumerate(unique_labels):
        cluster_pts = X[labels == label]
        if len(cluster_pts) == 0:
            continue
        centroids[i] = np.mean(cluster_pts, axis=0)
        s[i] = np.mean(np.linalg.norm(cluster_pts - centroids[i], axis=1))

    centroid_dists = euclidean_dist_matrix(centroids)

    r = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            if i != j and centroid_dists[i, j] > 0:
                r[i, j] = (s[i] + s[j]) / centroid_dists[i, j]
            else:
                r[i, j] = 0.0

    max_r = np.max(r, axis=1)
    return float(np.mean(max_r))


# ============================================================
# CLUSTERING ALGORITHMS (K-MEANS & DBSCAN)
# ============================================================

class NumpyKMeans:
    """K-Means clustering with K-Means++ initialization and Lloyd's iterations."""
    def __init__(self, n_clusters: int = 8, max_iter: int = 300, n_init: int = 10, random_state: int = 42):
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.n_init = n_init
        self.random_state = random_state
        self.cluster_centers_ = None
        self.labels_ = None
        self.inertia_ = None

    def fit(self, X: np.ndarray) -> "NumpyKMeans":
        rng = np.random.RandomState(self.random_state)
        n_samples, n_features = X.shape

        best_inertia = np.inf
        best_centers = None
        best_labels = None

        for init_idx in range(self.n_init):
            centers = np.empty((self.n_clusters, n_features))
            first_idx = rng.randint(0, n_samples)
            centers[0] = X[first_idx]

            for c_idx in range(1, self.n_clusters):
                dists = euclidean_dist_matrix(X, centers[:c_idx])
                min_sq_dists = np.min(dists, axis=1) ** 2
                sum_sq_dists = np.sum(min_sq_dists)
                if sum_sq_dists > 0:
                    probs = min_sq_dists / sum_sq_dists
                    chosen_idx = rng.choice(n_samples, p=probs)
                else:
                    chosen_idx = rng.randint(0, n_samples)
                centers[c_idx] = X[chosen_idx]

            for iter_idx in range(self.max_iter):
                dists = euclidean_dist_matrix(X, centers)
                labels = np.argmin(dists, axis=1)

                new_centers = np.empty_like(centers)
                for k in range(self.n_clusters):
                    mask = (labels == k)
                    if np.any(mask):
                        new_centers[k] = np.mean(X[mask], axis=0)
                    else:
                        new_centers[k] = X[rng.randint(0, n_samples)]

                if np.allclose(centers, new_centers, atol=1e-6):
                    break
                centers = new_centers

            dists = euclidean_dist_matrix(X, centers)
            min_dists = np.min(dists, axis=1)
            inertia = np.sum(min_dists ** 2)

            if inertia < best_inertia:
                best_inertia = inertia
                best_centers = centers.copy()
                best_labels = labels.copy()

        self.cluster_centers_ = best_centers
        self.labels_ = best_labels
        self.inertia_ = float(best_inertia)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        dists = euclidean_dist_matrix(X, self.cluster_centers_)
        return np.argmin(dists, axis=1)


def run_dbscan(X: np.ndarray, eps: float, min_samples: int) -> np.ndarray:
    """Density-Based Spatial Clustering of Applications with Noise (DBSCAN)."""
    n = X.shape[0]
    dist_mat = euclidean_dist_matrix(X)

    labels = np.full(n, -1, dtype=int)
    cluster_id = 0
    visited = np.zeros(n, dtype=bool)

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True

        neighbors = np.where(dist_mat[i] <= eps)[0]
        if len(neighbors) < min_samples:
            labels[i] = -1
        else:
            labels[i] = cluster_id
            seeds = list(neighbors)
            while seeds:
                curr_pt = seeds.pop(0)
                if not visited[curr_pt]:
                    visited[curr_pt] = True
                    curr_neighbors = np.where(dist_mat[curr_pt] <= eps)[0]
                    if len(curr_neighbors) >= min_samples:
                        seeds.extend([p for p in curr_neighbors if p not in seeds])
                if labels[curr_pt] == -1:
                    labels[curr_pt] = cluster_id
            cluster_id += 1

    return labels


# ============================================================
# PIPELINE EXECUTION
# ============================================================

def cluster_behavioral_peers():
    print("============================================================")
    print("ARGUS M2 STAGE 3: BEHAVIORAL PEER GROUP CLUSTERING")
    print("============================================================")

    # ------------------------------------------------------------
    # 1. READ STAGE 1 DAILY FEATURES
    # ------------------------------------------------------------
    print("\n[1/6] Loading Stage 1 daily feature dataset...")
    if not os.path.exists(INPUT_STAGE1_FEATURES):
        raise FileNotFoundError(f"Missing input Stage 1 dataset: {INPUT_STAGE1_FEATURES}")

    df_stage1 = pq.read_table(INPUT_STAGE1_FEATURES).to_pandas()
    total_records = len(df_stage1)
    total_users = df_stage1["user_id"].nunique()
    print(f"  -> Total daily observations: {total_records:>10,d}")
    print(f"  -> Total unique users:        {total_users:>10,d}")

    # ------------------------------------------------------------
    # 2. DEFINE TRAINING PERIOD & PROFILE FEATURE AGGREGATION
    # ------------------------------------------------------------
    print(f"\n[2/6] Aggregating 10-D profile vectors over baseline window [{TRAIN_START_DATE} to {TRAIN_END_DATE}]...")

    train_mask = (df_stage1["date"] >= TRAIN_START_DATE) & (df_stage1["date"] <= TRAIN_END_DATE)
    df_train = df_stage1[train_mask].copy()
    train_users = df_train["user_id"].nunique()

    print(f"  -> Training window records:   {len(df_train):>10,d}")
    print(f"  -> Users active in window:    {train_users:>10,d} / {total_users:,d}")

    if train_users != total_users:
        raise ValueError(f"Expected all {total_users} users in training window, but found {train_users}")

    # Vectorized computation of 10 profile dimensions
    df_train["off_hours_events_count"] = df_train["off_hours_event_ratio_1d"] * df_train["total_activity_count_1d"]
    df_train["exfil_events_count"] = df_train["cloud_storage_visit_count_1d"] + df_train["file_sharing_visit_count_1d"]

    grouped = df_train.groupby("user_id").agg(
        profile_mean_daily_logins=("login_count_1d", "mean"),
        profile_mean_daily_http=("http_request_count_1d", "mean"),
        profile_mean_daily_usb=("usb_connect_count_1d", "mean"),
        sum_off_hours=("off_hours_events_count", "sum"),
        sum_total_activity=("total_activity_count_1d", "sum"),
        profile_active_span_hours=("active_span_hours_1d", "mean"),
        sum_tech=("technology_visit_count_1d", "sum"),
        sum_social=("social_media_visit_count_1d", "sum"),
        sum_exfil=("exfil_events_count", "sum"),
        sum_http=("http_request_count_1d", "sum"),
        profile_distinct_domains_mean=("distinct_domains_count_1d", "mean"),
        profile_distinct_devices_mean=("distinct_devices_count_1d", "mean")
    ).reset_index()

    # Ratios with safe non-zero denominators
    grouped["profile_off_hours_ratio"] = grouped["sum_off_hours"] / grouped["sum_total_activity"].clip(lower=1)
    grouped["profile_tech_web_ratio"] = grouped["sum_tech"] / grouped["sum_http"].clip(lower=1)
    grouped["profile_social_web_ratio"] = grouped["sum_social"] / grouped["sum_http"].clip(lower=1)
    grouped["profile_exfiltration_web_ratio"] = grouped["sum_exfil"] / grouped["sum_http"].clip(lower=1)

    profiles_df = grouped[["user_id"] + PROFILE_FEATURE_COLUMNS].sort_values("user_id").reset_index(drop=True)
    print(f"  -> Profile matrix computed for {len(profiles_df)} users with 10 features.")

    # Display profile feature summary statistics
    print("\n  Profile Feature Summary Statistics (N=1,000 users):")
    summary_stats = profiles_df[PROFILE_FEATURE_COLUMNS].describe().T[["count", "mean", "std", "min", "50%", "max"]]
    print(summary_stats.to_string())

    # ------------------------------------------------------------
    # 3. FEATURE SCALING (FIT ON TRAINING PROFILE ONLY)
    # ------------------------------------------------------------
    print("\n[3/6] Fitting StandardScaler on training baseline profiles...")
    X = profiles_df[PROFILE_FEATURE_COLUMNS].values
    scaler = NumpyStandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ------------------------------------------------------------
    # 4. COMPREHENSIVE CLUSTERING EVALUATION
    # ------------------------------------------------------------
    print("\n[4/6] Evaluating K-Means (K=4..12) and DBSCAN parameter grid...")

    eval_records = []

    # K-Means Grid
    print("\n--- K-Means Evaluation Table ---")
    print(f"{'Algorithm':<10} | {'K':>3} | {'Inertia':>10} | {'Silhouette':>12} | {'Davies-Bouldin':>16}")
    print("-" * 62)
    kmeans_models = {}
    for k in range(4, 13):
        km = NumpyKMeans(n_clusters=k, random_state=RANDOM_SEED, n_init=10)
        km.fit(X_scaled)
        sil = compute_silhouette_score(X_scaled, km.labels_)
        db = compute_davies_bouldin_index(X_scaled, km.labels_)
        kmeans_models[k] = (km, sil, db)

        eval_records.append({
            "algorithm": "K-Means",
            "parameters": f"k={k}",
            "n_clusters": k,
            "n_noise": 0,
            "inertia": km.inertia_,
            "silhouette_score": sil,
            "davies_bouldin_index": db
        })
        print(f"{'K-Means':<10} | {k:3d} | {km.inertia_:10.2f} | {sil:12.4f} | {db:16.4f}")

    # DBSCAN Grid
    print("\n--- DBSCAN Evaluation Table ---")
    print(f"{'Algorithm':<10} | {'eps':>5} | {'min_samples':>11} | {'clusters':>8} | {'noise':>6} | {'Silhouette':>12} | {'Davies-Bouldin':>16}")
    print("-" * 82)
    for eps in [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]:
        for min_samples in [3, 5, 10, 15, 20]:
            db_labels = run_dbscan(X_scaled, eps=eps, min_samples=min_samples)
            n_clusters = len(set(db_labels)) - (1 if -1 in db_labels else 0)
            n_noise = int(np.sum(db_labels == -1))

            sil = compute_silhouette_score(X_scaled, db_labels)
            db = compute_davies_bouldin_index(X_scaled, db_labels)

            eval_records.append({
                "algorithm": "DBSCAN",
                "parameters": f"eps={eps:.2f}, min_samples={min_samples}",
                "n_clusters": n_clusters,
                "n_noise": n_noise,
                "inertia": np.nan,
                "silhouette_score": sil,
                "davies_bouldin_index": db
            })

            sil_str = f"{sil:12.4f}" if not np.isnan(sil) else f"{'N/A':>12}"
            db_str = f"{db:16.4f}" if not np.isnan(db) else f"{'N/A':>16}"
            print(f"{'DBSCAN':<10} | {eps:5.2f} | {min_samples:11d} | {n_clusters:8d} | {n_noise:6d} | {sil_str} | {db_str}")

    # Save evaluation table
    eval_df = pd.DataFrame(eval_records)
    eval_df.to_csv(OUTPUT_EVALUATION_CSV, index=False)
    print(f"\n  -> Clustering evaluation matrix exported to {OUTPUT_EVALUATION_CSV}")

    # ------------------------------------------------------------
    # 5. EMPIRICAL MODEL SELECTION & CLUSTER DESCRIPTIVE STATS
    # ------------------------------------------------------------
    # Selected candidate model: K-Means (K=7) as an empirical candidate
    # (Achieves lowest Davies-Bouldin index 0.7309 and balanced peer groups)
    SELECTED_K = 7
    selected_km, selected_sil, selected_db = kmeans_models[SELECTED_K]
    peer_labels = selected_km.labels_

    profiles_df["peer_group_id"] = peer_labels.astype(int)

    print(f"\n[5/6] Descriptive Behavioral Statistics for Selected Model: K-Means (K={SELECTED_K})")
    print(f"  -> Model Silhouette Score:     {selected_sil:.4f}")
    print(f"  -> Model Davies-Bouldin Index: {selected_db:.4f}")

    cluster_stats = profiles_df.groupby("peer_group_id").agg(
        user_count=("user_id", "count"),
        mean_logins=("profile_mean_daily_logins", "mean"),
        mean_http=("profile_mean_daily_http", "mean"),
        mean_usb=("profile_mean_daily_usb", "mean"),
        mean_off_hours_ratio=("profile_off_hours_ratio", "mean"),
        mean_active_span=("profile_active_span_hours", "mean"),
        mean_tech_ratio=("profile_tech_web_ratio", "mean"),
        mean_social_ratio=("profile_social_web_ratio", "mean"),
        mean_cloud_file_ratio=("profile_exfiltration_web_ratio", "mean"),
        mean_domains=("profile_distinct_domains_mean", "mean"),
        mean_devices=("profile_distinct_devices_mean", "mean")
    )
    print("\n" + cluster_stats.to_string())

    # ------------------------------------------------------------
    # 6. EXPORT USER PEER CLUSTERS PARQUET DATASET
    # ------------------------------------------------------------
    print("\n[6/6] Formatting and exporting user peer clusters dataset...")

    # Build profile vector column as list of 10 float values
    profile_vectors = profiles_df[PROFILE_FEATURE_COLUMNS].values.tolist()

    output_df = pd.DataFrame({
        "user_id": profiles_df["user_id"].astype(str),
        "peer_group_id": profiles_df["peer_group_id"].astype(np.int32),
        "clustering_algorithm": f"kmeans_k{SELECTED_K}",
        "cluster_silhouette_score": float(selected_sil),
        "profile_vector": profile_vectors
    })

    # Exact PyArrow Schema Definition
    schema = pa.schema([
        pa.field("user_id", pa.string(), nullable=False),
        pa.field("peer_group_id", pa.int32(), nullable=False),
        pa.field("clustering_algorithm", pa.string(), nullable=False),
        pa.field("cluster_silhouette_score", pa.float64(), nullable=False),
        pa.field("profile_vector", pa.list_(pa.float64()), nullable=False)
    ])

    table = pa.Table.from_pandas(output_df, schema=schema, preserve_index=False)
    pq.write_table(table, OUTPUT_PEER_CLUSTERS, compression="snappy")

    print(f"  -> User peer clusters successfully written to: {OUTPUT_PEER_CLUSTERS}")
    print(f"  -> Total users assigned: {len(output_df):,d} (1 assignment per user)")
    print("============================================================\n")


if __name__ == "__main__":
    cluster_behavioral_peers()
