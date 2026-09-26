from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler

from ml.integration.m1_to_m2 import load_m1_features
from ml.features.user_profile import build_user_profile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "ml" / "evaluation" / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

K = 3
RANDOM_SEEDS = [0, 1, 2, 3, 4, 42]


def main():
    # ---------------------------------------------------------
    # 1. Build the same 1,000-user feature matrix
    # ---------------------------------------------------------
    daily_features = load_m1_features()
    profile = build_user_profile(daily_features)

    feature_columns = [
        column
        for column in profile.columns
        if column != "user_id"
    ]

    X = profile[feature_columns]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print("=" * 60)
    print("ARGUS K-MEANS CLUSTER STABILITY")
    print("=" * 60)
    print(f"Users              : {len(profile):,}")
    print(f"Features            : {len(feature_columns)}")
    print(f"K                  : {K}")
    print(f"Random seeds        : {RANDOM_SEEDS}")
    print()

    # ---------------------------------------------------------
    # 2. Run K-Means with multiple seeds
    # ---------------------------------------------------------
    assignments = {}

    for seed in RANDOM_SEEDS:
        model = KMeans(
            n_clusters=K,
            random_state=seed,
            n_init=10,
        )

        labels = model.fit_predict(X_scaled)

        assignments[seed] = labels

        sizes = (
            pd.Series(labels)
            .value_counts()
            .sort_index()
            .tolist()
        )

        print(
            f"Seed={seed:<2} | "
            f"Cluster sizes={sizes} | "
            f"Inertia={model.inertia_:.6f}"
        )

    # ---------------------------------------------------------
    # 3. Compare every run against seed 42
    # ---------------------------------------------------------
    reference_seed = 42
    reference_labels = assignments[reference_seed]

    stability_results = []

    for seed in RANDOM_SEEDS:
        ari = adjusted_rand_score(
            reference_labels,
            assignments[seed],
        )

        stability_results.append(
            {
                "reference_seed": reference_seed,
                "comparison_seed": seed,
                "adjusted_rand_index": ari,
            }
        )

    stability_df = pd.DataFrame(stability_results)

    stability_df.to_csv(
        OUTPUT_DIR / "kmeans_k3_stability.csv",
        index=False,
    )

    print("\nStability relative to seed 42:")
    print(
        stability_df.round(6).to_string(index=False)
    )

    # ---------------------------------------------------------
    # 4. Pairwise stability across all runs
    # ---------------------------------------------------------
    pairwise_results = []

    for i, seed_a in enumerate(RANDOM_SEEDS):
        for seed_b in RANDOM_SEEDS[i + 1:]:
            ari = adjusted_rand_score(
                assignments[seed_a],
                assignments[seed_b],
            )

            pairwise_results.append(
                {
                    "seed_a": seed_a,
                    "seed_b": seed_b,
                    "adjusted_rand_index": ari,
                }
            )

    pairwise_df = pd.DataFrame(pairwise_results)

    pairwise_df.to_csv(
        OUTPUT_DIR / "kmeans_k3_pairwise_stability.csv",
        index=False,
    )

    print("\nPairwise stability:")
    print(
        pairwise_df.round(6).to_string(index=False)
    )

    print("\nOutput files:")
    print(
        OUTPUT_DIR / "kmeans_k3_stability.csv"
    )
    print(
        OUTPUT_DIR / "kmeans_k3_pairwise_stability.csv"
    )

    print("\nCluster stability analysis completed successfully.")


if __name__ == "__main__":
    main()