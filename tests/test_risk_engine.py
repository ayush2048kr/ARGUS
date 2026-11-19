
import pytest

from ml.risk.risk_engine import calculate_risk, get_risk_level


def test_equal_weight_fusion():
    result = calculate_risk(20, 60)
    assert result["risk_score"] == 40.0
    assert result["risk_level"] == "MEDIUM"


def test_context_score_is_included_when_available():
    result = calculate_risk(20, 40, 90)
    assert result["risk_score"] == 50.0
    assert "context" in result["components_used"]


def test_missing_score_is_not_treated_as_zero():
    result = calculate_risk(60, None)
    assert result["risk_score"] == 60.0
    assert result["components_used"] == ["behavioral_deviation"]


def test_no_evidence_returns_unavailable():
    result = calculate_risk(None, None)
    assert result["risk_score"] is None
    assert result["risk_level"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "LOW"),
        (30, "LOW"),
        (31, "MEDIUM"),
        (60, "MEDIUM"),
        (61, "HIGH"),
        (80, "HIGH"),
        (81, "CRITICAL"),
        (100, "CRITICAL"),
    ],
)
def test_risk_bands(score, expected):
    assert get_risk_level(score) == expected


@pytest.mark.parametrize("score", [-1, 101, float("nan"), float("inf")])
def test_invalid_scores_are_rejected(score):
    with pytest.raises(ValueError):
        calculate_risk(score, 50)


def test_explanation_is_included():
    result = calculate_risk(
        70,
        40,
        behavioral_explanation="Activity differs from historical baseline.",
        peer_explanation="HTTP activity is above peers.",
    )
    assert "historical baseline" in result["explanation"]
    assert "above peers" in result["explanation"]
