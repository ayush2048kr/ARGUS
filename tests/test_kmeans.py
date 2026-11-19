import pandas as pd

from ml.clustering.kmeans import perform_kmeans


def test_kmeans_clustering():
    features = pd.DataFrame(
        {
            "activity_frequency": [1.0, 1.2, 10.0, 10.2],
            "resource_access_frequency": [1.0, 1.1, 10.0, 10.1],
            "unique_resource_count": [1.0, 1.2, 9.0, 9.2],
        }
    )

    labels, model = perform_kmeans(
        features,
        n_clusters=2,
    )

    assert len(labels) == 4
    assert model.n_clusters == 2

    # First two users should be in the same behavioral group.
    assert labels.iloc[0] == labels.iloc[1]

    # Last two users should be in the same behavioral group.
    assert labels.iloc[2] == labels.iloc[3]

    # The two behavioral groups should be different.
    assert labels.iloc[0] != labels.iloc[2]