from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.decomposition import PCA, KernelPCA
from sklearn.preprocessing import StandardScaler
from umap import UMAP

from ml.integration.m1_to_m2 import load_m1_features
from ml.features.user_profile import build_user_profile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "ml" / "evaluation" / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def plot_representation(
    embedding,
    title,
    xlabel,
    ylabel,
    output_path,
):
    fig, ax = plt.subplots(figsize=(10, 7))

    ax.scatter(
        embedding[:, 0],
        embedding[:, 1],
        s=18,
        alpha=0.7,
    )

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.2)

    fig.tight_layout()
    fig.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig)


def main():
    # ---------------------------------------------------------
    # 1. Load M1 -> M2 integrated data
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

    print("=" * 60)
    print("ARGUS DIMENSIONALITY REDUCTION")
    print("=" * 60)
    print(f"Users              : {len(X):,}")
    print(f"Input features     : {len(feature_columns)}")
    print()

    # ---------------------------------------------------------
    # 3. Standardize the feature space
    # ---------------------------------------------------------
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print("Standardization completed.")

    # ---------------------------------------------------------
    # 4. PCA
    # ---------------------------------------------------------
    pca = PCA(
        n_components=2,
        random_state=42,
    )

    X_pca = pca.fit_transform(X_scaled)

    pca_variance = pca.explained_variance_ratio_

    print("\nPCA")
    print(f"PC1 explained variance : {pca_variance[0]:.6f}")
    print(f"PC2 explained variance : {pca_variance[1]:.6f}")
    print(
        f"Total 2D variance     : "
        f"{pca_variance.sum():.6f}"
    )

    pca_output = pd.DataFrame(
        {
            "user_id": profile["user_id"],
            "PC1": X_pca[:, 0],
            "PC2": X_pca[:, 1],
        }
    )

    pca_output.to_csv(
        OUTPUT_DIR / "pca_2d.csv",
        index=False,
    )

    pd.DataFrame(
        {
            "component": ["PC1", "PC2"],
            "explained_variance_ratio": pca_variance,
        }
    ).to_csv(
        OUTPUT_DIR / "pca_explained_variance.csv",
        index=False,
    )

    plot_representation(
        X_pca,
        "ARGUS PCA — 2D User Representation",
        "Principal Component 1",
        "Principal Component 2",
        OUTPUT_DIR / "pca_2d_scatter.png",
    )

    # ---------------------------------------------------------
    # 5. Kernel PCA with RBF kernel
    # ---------------------------------------------------------
    kpca = KernelPCA(
        n_components=2,
        kernel="rbf",
        gamma=1.0 / len(feature_columns),
        random_state=42,
    )

    X_kpca = kpca.fit_transform(X_scaled)

    print("\nRBF Kernel PCA")
    print(f"Kernel             : RBF")
    print(
        f"Gamma              : "
        f"{1.0 / len(feature_columns):.6f}"
    )
    print(f"Output dimensions  : {X_kpca.shape[1]}")

    kpca_output = pd.DataFrame(
        {
            "user_id": profile["user_id"],
            "KPCA1": X_kpca[:, 0],
            "KPCA2": X_kpca[:, 1],
        }
    )

    kpca_output.to_csv(
        OUTPUT_DIR / "kpca_rbf_2d.csv",
        index=False,
    )

    plot_representation(
        X_kpca,
        "ARGUS RBF Kernel PCA — 2D User Representation",
        "Kernel Principal Component 1",
        "Kernel Principal Component 2",
        OUTPUT_DIR / "kpca_rbf_2d_scatter.png",
    )

    # ---------------------------------------------------------
    # 6. UMAP
    # ---------------------------------------------------------
    umap_model = UMAP(
        n_components=2,
        n_neighbors=15,
        min_dist=0.1,
        metric="euclidean",
        random_state=42,
    )

    X_umap = umap_model.fit_transform(X_scaled)

    print("\nUMAP")
    print("Components         : 2")
    print("Neighbors          : 15")
    print("Minimum distance   : 0.1")
    print("Metric             : euclidean")

    umap_output = pd.DataFrame(
        {
            "user_id": profile["user_id"],
            "UMAP1": X_umap[:, 0],
            "UMAP2": X_umap[:, 1],
        }
    )

    umap_output.to_csv(
        OUTPUT_DIR / "umap_2d.csv",
        index=False,
    )

    plot_representation(
        X_umap,
        "ARGUS UMAP — 2D User Representation",
        "UMAP Dimension 1",
        "UMAP Dimension 2",
        OUTPUT_DIR / "umap_2d_scatter.png",
    )

    # ---------------------------------------------------------
    # 7. Combined summary
    # ---------------------------------------------------------
    summary = pd.DataFrame(
        {
            "method": [
                "PCA",
                "RBF Kernel PCA",
                "UMAP",
            ],
            "input_dimensions": [
                X_scaled.shape[1],
                X_scaled.shape[1],
                X_scaled.shape[1],
            ],
            "output_dimensions": [
                X_pca.shape[1],
                X_kpca.shape[1],
                X_umap.shape[1],
            ],
        }
    )

    summary.to_csv(
        OUTPUT_DIR / "dimensionality_reduction_summary.csv",
        index=False,
    )

    print("\nOutput files:")
    for filename in [
        "pca_2d.csv",
        "pca_explained_variance.csv",
        "pca_2d_scatter.png",
        "kpca_rbf_2d.csv",
        "kpca_rbf_2d_scatter.png",
        "umap_2d.csv",
        "umap_2d_scatter.png",
        "dimensionality_reduction_summary.csv",
    ]:
        print(OUTPUT_DIR / filename)

    print("\nDimensionality reduction completed successfully.")


if __name__ == "__main__":
    main()