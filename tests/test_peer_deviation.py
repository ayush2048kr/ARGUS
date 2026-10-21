
import numpy as np
import pandas as pd
import pytest

from ml.deviation.peer_deviation import calculate_peer_deviation


def sample_data():
    profiles = pd.DataFrame({
        "user_id": [f"EMP{i:03}" for i in range(1, 8)],
        "activity": [10, 11, 9, 10, 12, 10, 100],
        "usb": [1, 1, 2, 1, 2, 1, 20],
    })
    assignments = pd.DataFrame({
        "user_id": profiles["user_id"],
        "cluster_id": [0, 0, 0, 0, 0, 0, 1],
    })
    return profiles, assignments


def test_peer_scores_are_bounded():
    profiles, assignments = sample_data()

    result = calculate_peer_deviation(
        profiles, assignments,
        feature_columns=["activity", "usb"],
        min_peers=5,
    )

    available = result.loc[
        result["peer_deviation_status"] == "available",
        "peer_deviation_score",
    ]

    assert available.notna().all()
    assert available.between(0, 100).all()


def test_user_with_too_few_peers_has_no_score():
    profiles, assignments = sample_data()

    result = calculate_peer_deviation(
        profiles, assignments,
        feature_columns=["activity", "usb"],
        min_peers=5,
    )

    isolated = result.set_index("user_id").loc["EMP007"]

    assert isolated["peer_count"] == 0
    assert isolated["peer_deviation_status"] == "insufficient_peers"
    assert np.isnan(isolated["peer_deviation_score"])


def test_peer_statistics_exclude_the_user():
    profiles, assignments = sample_data()

    result = calculate_peer_deviation(
        profiles, assignments,
        feature_columns=["activity", "usb"],
        min_peers=5,
    )

    indexed = result.set_index("user_id")
    ordinary_score = indexed.loc["EMP001", "peer_deviation_score"]

    profiles_changed = profiles.copy()
    profiles_changed.loc[
        profiles_changed["user_id"] == "EMP001", "activity"
    ] = 500

    changed = calculate_peer_deviation(
        profiles_changed, assignments,
        feature_columns=["activity", "usb"],
        min_peers=5,
    ).set_index("user_id")

    assert changed.loc["EMP001", "peer_deviation_score"] > ordinary_score


def test_missing_profile_assignment_is_rejected():
    profiles, assignments = sample_data()
    assignments = assignments.iloc[:-1].copy()

    with pytest.raises(ValueError, match="mismatch"):
        calculate_peer_deviation(
            profiles, assignments,
            feature_columns=["activity", "usb"],
        )


def test_duplicate_users_are_rejected():
    profiles, assignments = sample_data()
    profiles = pd.concat([profiles, profiles.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate"):
        calculate_peer_deviation(
            profiles, assignments,
            feature_columns=["activity", "usb"],
        )
