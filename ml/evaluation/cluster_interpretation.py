from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "ml" / "evaluation" / "output"

CENTROID_PATH = OUTPUT_DIR / "kmeans_k3_standardized_centroids.csv"


def main():
    if not CENTROID_PATH.exists():
        raise FileNotFoundError(
            f"Centroid file not found: {CENTROID_PATH}"
        )

    centroids = pd.read_csv(
        CENTROID_PATH,
        index_col="cluster_id",
    )

    print("=" * 60)
    print("ARGUS CLUSTER INTERPRETATION")
    print("=" * 60)

    print("\nStandardized cluster centroids:")
    print(centroids.round(4).to_string())

    # ---------------------------------------------------------
    # Difference from overall standardized population mean.
    #
    # Since the input features were standardized before K-Means,
    # the overall feature mean is approximately 0.
    # Therefore, centroid values indicate whether a cluster
    # is above or below the overall population average.
    # ---------------------------------------------------------
    interpretation_rows = []

    for cluster_id in centroids.index:
        cluster_values = centroids.loc[cluster_id]

        sorted_features = (
            cluster_values
            .abs()
            .sort_values(ascending=False)
        )

        for feature in sorted_features.index:
            z_value = cluster_values[feature]

            interpretation_rows.append(
                {
                    "cluster_id": cluster_id,
                    "feature": feature,
                    "standardized_centroid": z_value,
                    "absolute_deviation": abs(z_value),
                    "direction": (
                        "above_population_average"
                        if z_value > 0
                        else "below_population_average"
                    ),
                }
            )

    interpretation = pd.DataFrame(
        interpretation_rows
    )

    interpretation.to_csv(
        OUTPUT_DIR / "kmeans_k3_cluster_feature_deviations.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # Top 5 distinguishing features per cluster
    # ---------------------------------------------------------
    top_features = (
        interpretation
        .sort_values(
            ["cluster_id", "absolute_deviation"],
            ascending=[True, False],
        )
        .groupby("cluster_id")
        .head(5)
    )

    top_features.to_csv(
        OUTPUT_DIR / "kmeans_k3_top_features.csv",
        index=False,
    )

    print("\nTop 5 distinguishing features per cluster:")

    for cluster_id in sorted(centroids.index):
        cluster_top = top_features[
            top_features["cluster_id"] == cluster_id
        ]

        print(f"\nCluster {cluster_id}")

        for _, row in cluster_top.iterrows():
            print(
                f"  {row['feature']}: "
                f"{row['standardized_centroid']:.4f} "
                f"({row['direction']})"
            )

    print("\nOutput files:")
    print(
        OUTPUT_DIR
        / "kmeans_k3_cluster_feature_deviations.csv"
    )
    print(
        OUTPUT_DIR
        / "kmeans_k3_top_features.csv"
    )

    print("\nCluster interpretation completed successfully.")


if __name__ == "__main__":
    main()