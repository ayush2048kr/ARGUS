from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from ml.integration.m1_to_m2 import load_m1_features
from ml.features.user_profile import build_user_profile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "ml" / "evaluation" / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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
        column for column in profile.columns
        if column != "user_id"
    ]

    # ---------------------------------------------------------
    # 3. Generate descriptive statistics
    # ---------------------------------------------------------
    statistics = profile[feature_columns].describe().T

    statistics["missing_values"] = (
        profile[feature_columns].isnull().sum()
    )

    statistics["zero_values"] = (
        (profile[feature_columns] == 0).sum()
    )

    statistics["unique_values"] = (
        profile[feature_columns].nunique()
    )

    statistics["skewness"] = (
        profile[feature_columns].skew()
    )

    statistics.to_csv(
        OUTPUT_DIR / "feature_distribution_statistics.csv"
    )

    # ---------------------------------------------------------
    # 4. Create distribution plots
    # ---------------------------------------------------------
    n_features = len(feature_columns)
    n_columns = 3
    n_rows = (n_features + n_columns - 1) // n_columns

    fig, axes = plt.subplots(
        n_rows,
        n_columns,
        figsize=(18, 4 * n_rows)
    )

    axes = axes.flatten()

    for index, feature in enumerate(feature_columns):
        axes[index].hist(
            profile[feature],
            bins=30,
            edgecolor="black"
        )

        axes[index].set_title(feature)
        axes[index].set_xlabel("Value")
        axes[index].set_ylabel("Number of Users")
        axes[index].grid(alpha=0.2)

    # Hide unused axes
    for index in range(n_features, len(axes)):
        axes[index].set_visible(False)

    fig.suptitle(
        "ARGUS User Behavioral Feature Distributions",
        fontsize=16
    )

    fig.tight_layout()

    fig.savefig(
        OUTPUT_DIR / "feature_distributions.png",
        dpi=200,
        bbox_inches="tight"
    )

    plt.close(fig)

    # ---------------------------------------------------------
    # 5. Create boxplot for all standardized features
    # ---------------------------------------------------------
    standardized_profile = profile[feature_columns].copy()

    for feature in feature_columns:
        mean = standardized_profile[feature].mean()
        std = standardized_profile[feature].std()

        if std != 0:
            standardized_profile[feature] = (
                standardized_profile[feature] - mean
            ) / std
        else:
            standardized_profile[feature] = 0

    fig, ax = plt.subplots(
        figsize=(18, 8)
    )

    ax.boxplot(
        [
            standardized_profile[feature]
            for feature in feature_columns
        ],
        labels=feature_columns
    )

    ax.set_title(
        "Standardized ARGUS Behavioral Feature Distribution"
    )

    ax.set_ylabel("Standardized Value")
    ax.tick_params(axis="x", rotation=75)
    ax.grid(axis="y", alpha=0.2)

    fig.tight_layout()

    fig.savefig(
        OUTPUT_DIR / "standardized_feature_boxplot.png",
        dpi=200,
        bbox_inches="tight"
    )

    plt.close(fig)

    # ---------------------------------------------------------
    # 6. Print summary
    # ---------------------------------------------------------
    print("=" * 60)
    print("ARGUS FEATURE DISTRIBUTION ANALYSIS")
    print("=" * 60)

    print(f"Users              : {len(profile):,}")
    print(f"Features            : {len(feature_columns)}")
    print(
        f"Missing values      : "
        f"{int(profile[feature_columns].isnull().sum().sum())}"
    )

    print("\nFeature statistics:")
    print(
        statistics[
            [
                "mean",
                "std",
                "min",
                "max",
                "zero_values",
                "unique_values",
                "skewness",
            ]
        ].round(4).to_string()
    )

    print("\nOutput files:")
    print(
        OUTPUT_DIR / "feature_distribution_statistics.csv"
    )
    print(
        OUTPUT_DIR / "feature_distributions.png"
    )
    print(
        OUTPUT_DIR / "standardized_feature_boxplot.png"
    )

    print("\nFeature distribution analysis completed.")


if __name__ == "__main__":
    main()