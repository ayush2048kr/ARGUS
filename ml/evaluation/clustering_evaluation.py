from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from sklearn.metrics import (
    silhouette_score,
    davies_bouldin_score,
)
from sklearn.preprocessing import StandardScaler

from ml.integration.m1_to_m2 import load_m1_features
from ml.features.user_profile import build_user_profile
from ml.clustering.kmeans import perform_kmeans


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "ml" / "evaluation" / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


MIN_K = 2
MAX_K = 6


def main():
    # ---------------------------------------------------------
    # 1. Load integrated M1 -> M2 data
    # ---------------------------------------------------------
    daily_features = load_m1_features()

    # ---------------------------------------------------------
    # 2. Build one behavioral profile per user
    # ---------------------------------------------------------
    profile = build_user_profile(daily_features)

    feature_columns = [
        column
        for column in profile.columns
        if column != "user_id"
    ]

    X = profile[feature_columns].copy()

    # ---------------------------------------------------------
    # 3. Standardize the behavioral feature space
    # ---------------------------------------------------------
    scaler = StandardScaler()
    X_scaled_array = scaler.fit_transform(X)

    X_scaled = pd.DataFrame(
        X_scaled_array,
        columns=feature_columns,
        index=profile.index,
    )

    print("=" * 60)
    print("ARGUS K-MEANS CLUSTERING EVALUATION")
    print("=" * 60)
    print(f"Users              : {len(profile):,}")
    print(f"Input features     : {len(feature_columns)}")
    print(f"K range            : {MIN_K} - {MAX_K}")
    print()

    # ---------------------------------------------------------
    # 4. Evaluate multiple K values
    # ---------------------------------------------------------
    results = []

    for k in range(MIN_K, MAX_K + 1):

        labels, model = perform_kmeans(
            scaled_features=X_scaled,
            n_clusters=k,
            random_state=42,
        )

        silhouette = silhouette_score(
            X_scaled,
            labels,
        )

        davies_bouldin = davies_bouldin_score(
            X_scaled,
            labels,
        )

        results.append(
            {
                "k": k,
                "silhouette_score": silhouette,
                "davies_bouldin_index": davies_bouldin,
                "inertia": model.inertia_,
            }
        )

        print(
            f"K={k} | "
            f"Silhouette={silhouette:.6f} | "
            f"Davies-Bouldin={davies_bouldin:.6f} | "
            f"Inertia={model.inertia_:.6f}"
        )

    results_df = pd.DataFrame(results)

    # ---------------------------------------------------------
    # 5. Save metric table
    # ---------------------------------------------------------
    results_df.to_csv(
        OUTPUT_DIR / "kmeans_evaluation_metrics.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # 6. Silhouette plot
    # ---------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 6))

    ax.plot(
        results_df["k"],
        results_df["silhouette_score"],
        marker="o",
    )

    ax.set_title("K-Means: K vs Silhouette Score")
    ax.set_xlabel("Number of Clusters (K)")
    ax.set_ylabel("Silhouette Score")
    ax.set_xticks(results_df["k"])
    ax.grid(alpha=0.2)

    fig.tight_layout()

    fig.savefig(
        OUTPUT_DIR / "kmeans_silhouette.png",
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)

    # ---------------------------------------------------------
    # 7. Davies-Bouldin plot
    # ---------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 6))

    ax.plot(
        results_df["k"],
        results_df["davies_bouldin_index"],
        marker="o",
    )

    ax.set_title("K-Means: K vs Davies-Bouldin Index")
    ax.set_xlabel("Number of Clusters (K)")
    ax.set_ylabel("Davies-Bouldin Index")
    ax.set_xticks(results_df["k"])
    ax.grid(alpha=0.2)

    fig.tight_layout()

    fig.savefig(
        OUTPUT_DIR / "kmeans_davies_bouldin.png",
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)

    # ---------------------------------------------------------
    # 8. Inertia / Elbow plot
    # ---------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 6))

    ax.plot(
        results_df["k"],
        results_df["inertia"],
        marker="o",
    )

    ax.set_title("K-Means Elbow Curve")
    ax.set_xlabel("Number of Clusters (K)")
    ax.set_ylabel("Within-Cluster Sum of Squares (Inertia)")
    ax.set_xticks(results_df["k"])
    ax.grid(alpha=0.2)

    fig.tight_layout()

    fig.savefig(
        OUTPUT_DIR / "kmeans_elbow.png",
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)

    # ---------------------------------------------------------
    # 9. Print final table
    # ---------------------------------------------------------
    print("\nClustering evaluation results:")
    print(
        results_df.round(6).to_string(index=False)
    )

    print("\nOutput files:")
    print(
        OUTPUT_DIR / "kmeans_evaluation_metrics.csv"
    )
    print(
        OUTPUT_DIR / "kmeans_silhouette.png"
    )
    print(
        OUTPUT_DIR / "kmeans_davies_bouldin.png"
    )
    print(
        OUTPUT_DIR / "kmeans_elbow.png"
    )

    print("\nK-Means evaluation completed successfully.")


if __name__ == "__main__":
    main()