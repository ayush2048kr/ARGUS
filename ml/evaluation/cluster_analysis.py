from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from ml.integration.m1_to_m2 import load_m1_features
from ml.features.user_profile import build_user_profile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "ml" / "evaluation" / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

K = 3


def create_cluster_scatter(
    representation,
    labels,
    title,
    xlabel,
    ylabel,
    output_path,
):
    fig, ax = plt.subplots(figsize=(10, 7))

    scatter = ax.scatter(
        representation[:, 0],
        representation[:, 1],
        c=labels,
        s=20,
        alpha=0.75,
    )

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.2)

    legend = ax.legend(
        *scatter.legend_elements(),
        title="Cluster",
    )

    ax.add_artist(legend)

    fig.tight_layout()

    fig.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)


def main():
    # ---------------------------------------------------------
    # 1. Load integrated M1 -> M2 data
    # ---------------------------------------------------------
    daily_features = load_m1_features()

    # ---------------------------------------------------------
    # 2. Build user profiles
    # ---------------------------------------------------------
    profile = build_user_profile(daily_features)

    feature_columns = [
        column
        for column in profile.columns
        if column != "user_id"
    ]

    X = profile[feature_columns].copy()

    # ---------------------------------------------------------
    # 3. Standardize features
    # ---------------------------------------------------------
    scaler = StandardScaler()

    X_scaled = scaler.fit_transform(X)

    # ---------------------------------------------------------
    # 4. Perform K-Means using K=3
    # ---------------------------------------------------------
    model = KMeans(
        n_clusters=K,
        random_state=42,
        n_init=10,
    )

    labels = model.fit_predict(X_scaled)

    # ---------------------------------------------------------
    # 5. Save user -> cluster assignments
    # ---------------------------------------------------------
    assignments = pd.DataFrame(
        {
            "user_id": profile["user_id"],
            "cluster_id": labels,
        }
    )

    assignments.to_csv(
        OUTPUT_DIR / "kmeans_k3_user_clusters.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # 6. Cluster sizes
    # ---------------------------------------------------------
    cluster_sizes = (
        assignments["cluster_id"]
        .value_counts()
        .sort_index()
        .reset_index()
    )

    cluster_sizes.columns = [
        "cluster_id",
        "user_count",
    ]

    cluster_sizes["percentage"] = (
        cluster_sizes["user_count"]
        / len(assignments)
        * 100
    )

    cluster_sizes.to_csv(
        OUTPUT_DIR / "kmeans_k3_cluster_sizes.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # 7. Behavioral profile of each cluster
    #
    # These are means in the ORIGINAL feature scale,
    # making them easier to interpret.
    # ---------------------------------------------------------
    cluster_profiles = (
        profile[["user_id"] + feature_columns]
        .merge(
            assignments,
            on="user_id",
            how="inner",
            validate="one_to_one",
        )
        .groupby("cluster_id")[feature_columns]
        .mean()
    )

    cluster_profiles.to_csv(
        OUTPUT_DIR / "kmeans_k3_cluster_profiles.csv"
    )

    # ---------------------------------------------------------
    # 8. Standardized cluster centroids
    # ---------------------------------------------------------
    standardized_centroids = pd.DataFrame(
        model.cluster_centers_,
        columns=feature_columns,
    )

    standardized_centroids.index.name = "cluster_id"

    standardized_centroids.to_csv(
        OUTPUT_DIR / "kmeans_k3_standardized_centroids.csv"
    )

    # ---------------------------------------------------------
    # 9. Load existing PCA representation
    # ---------------------------------------------------------
    pca = pd.read_csv(
        OUTPUT_DIR / "pca_2d.csv"
    )

    pca = pca.merge(
        assignments,
        on="user_id",
        how="inner",
        validate="one_to_one",
    )

    create_cluster_scatter(
        pca[["PC1", "PC2"]].to_numpy(),
        pca["cluster_id"].to_numpy(),
        "ARGUS K-Means (K=3) on PCA Representation",
        "Principal Component 1",
        "Principal Component 2",
        OUTPUT_DIR / "kmeans_k3_pca_clusters.png",
    )

    # ---------------------------------------------------------
    # 10. Load existing Kernel PCA representation
    # ---------------------------------------------------------
    kpca = pd.read_csv(
        OUTPUT_DIR / "kpca_rbf_2d.csv"
    )

    kpca = kpca.merge(
        assignments,
        on="user_id",
        how="inner",
        validate="one_to_one",
    )

    create_cluster_scatter(
        kpca[["KPCA1", "KPCA2"]].to_numpy(),
        kpca["cluster_id"].to_numpy(),
        "ARGUS K-Means (K=3) on RBF Kernel PCA",
        "Kernel Principal Component 1",
        "Kernel Principal Component 2",
        OUTPUT_DIR / "kmeans_k3_kpca_clusters.png",
    )

    # ---------------------------------------------------------
    # 11. Load existing UMAP representation
    # ---------------------------------------------------------
    umap = pd.read_csv(
        OUTPUT_DIR / "umap_2d.csv"
    )

    umap = umap.merge(
        assignments,
        on="user_id",
        how="inner",
        validate="one_to_one",
    )

    create_cluster_scatter(
        umap[["UMAP1", "UMAP2"]].to_numpy(),
        umap["cluster_id"].to_numpy(),
        "ARGUS K-Means (K=3) on UMAP Representation",
        "UMAP Dimension 1",
        "UMAP Dimension 2",
        OUTPUT_DIR / "kmeans_k3_umap_clusters.png",
    )

    # ---------------------------------------------------------
    # 12. Print results
    # ---------------------------------------------------------
    print("=" * 60)
    print("ARGUS K-MEANS CLUSTER ANALYSIS")
    print("=" * 60)

    print(f"Users              : {len(profile):,}")
    print(f"Features            : {len(feature_columns)}")
    print(f"Clusters (K)        : {K}")

    print("\nCluster sizes:")
    print(
        cluster_sizes.to_string(index=False)
    )

    print("\nCluster behavioral profiles:")
    print(
        cluster_profiles.round(4).to_string()
    )

    print("\nOutput files:")
    print(
        OUTPUT_DIR / "kmeans_k3_user_clusters.csv"
    )
    print(
        OUTPUT_DIR / "kmeans_k3_cluster_sizes.csv"
    )
    print(
        OUTPUT_DIR / "kmeans_k3_cluster_profiles.csv"
    )
    print(
        OUTPUT_DIR / "kmeans_k3_standardized_centroids.csv"
    )
    print(
        OUTPUT_DIR / "kmeans_k3_pca_clusters.png"
    )
    print(
        OUTPUT_DIR / "kmeans_k3_kpca_clusters.png"
    )
    print(
        OUTPUT_DIR / "kmeans_k3_umap_clusters.png"
    )

    print("\nCluster analysis completed successfully.")


if __name__ == "__main__":
    main()