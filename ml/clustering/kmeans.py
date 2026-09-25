from sklearn.cluster import KMeans
import pandas as pd


def perform_kmeans(
    scaled_features: pd.DataFrame,
    n_clusters: int,
    random_state: int = 42,
) -> tuple[pd.Series, KMeans]:
    """
    Cluster users based on standardized behavioral features.

    Parameters
    ----------
    scaled_features : pd.DataFrame
        Standardized behavioral feature matrix.
        Each row represents one user.

    n_clusters : int
        Number of behavioral clusters.

    random_state : int
        Random seed for reproducibility.

    Returns
    -------
    tuple[pd.Series, KMeans]
        Cluster labels for each user and the fitted K-Means model.
    """

    if scaled_features.empty:
        raise ValueError("Scaled feature matrix is empty.")

    if n_clusters < 2:
        raise ValueError("n_clusters must be at least 2.")

    if n_clusters >= len(scaled_features):
        raise ValueError(
            "n_clusters must be smaller than the number of users."
        )

    model = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init=10,
    )

    cluster_labels = model.fit_predict(scaled_features)

    labels = pd.Series(
        cluster_labels,
        index=scaled_features.index,
        name="cluster_id",
    )

    return labels, model