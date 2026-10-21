
import numpy as np
import pandas as pd
import pytest

from ml.deviation.behavioral_deviation import (
    calculate_behavioral_deviation,
)


@pytest.fixture
def sample_history():
    return pd.DataFrame({
        "user_id": ["EMP001", "EMP001", "EMP002", "EMP003"],
        "date": [
            "2026-01-01",
            "2026-01-02",
            "2026-01-01",
            "2026-01-01",
        ],
        "has_sufficient_history": [True, True, False, True],
        "self_activity_drift_zscore": [0.0, 2.0, np.nan, np.nan],
    })


def test_scores_are_bounded_and_monotonic(sample_history):
    result = calculate_behavioral_deviation(sample_history)

    scores = result["behavioral_deviation_score"]

    assert scores.iloc[0] == 0.0
    assert scores.iloc[1] == 50.0
    assert scores.iloc[1] > scores.iloc[0]
    assert scores.iloc[2:].isna().all()


def test_baseline_status_is_explicit(sample_history):
    result = calculate_behavioral_deviation(sample_history)

    assert result["baseline_status"].tolist() == [
        "available",
        "available",
        "insufficient_history",
        "zscore_unavailable",
    ]


def test_large_deviation_saturates_at_100(sample_history):
    sample_history.loc[0, "self_activity_drift_zscore"] = -8.0

    result = calculate_behavioral_deviation(sample_history)

    assert result.loc[0, "behavioral_deviation_score"] == 100.0


def test_invalid_saturation_is_rejected(sample_history):
    with pytest.raises(ValueError):
        calculate_behavioral_deviation(
            sample_history,
            saturation_z=0,
        )


def test_duplicate_user_dates_are_rejected(sample_history):
    duplicate = pd.concat(
        [sample_history, sample_history.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="Duplicate"):
        calculate_behavioral_deviation(duplicate)


def test_infinite_zscore_is_rejected(sample_history):
    sample_history.loc[0, "self_activity_drift_zscore"] = np.inf

    with pytest.raises(ValueError, match="infinity"):
        calculate_behavioral_deviation(sample_history)
