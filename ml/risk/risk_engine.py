
"""ARGUS risk scoring using an adapted weighted-average fusion method.

Research basis:
Yuan et al. (2026), FusionITD:
https://link.springer.com/article/10.1186/s42400-026-00555-w

ARGUS adaptation:
- Fuses available normalized evidence scores.
- Uses equal weights as a provisional baseline.
- Does not claim to reproduce FusionITD or its learned weights.
- Produces an anomaly-risk indicator, not a probability of maliciousness.
"""

import math
from typing import Any


RISK_BANDS = (
    (30, "LOW"),
    (60, "MEDIUM"),
    (80, "HIGH"),
    (100, "CRITICAL"),
)


def get_risk_level(score: float) -> str:
    """Map a 0–100 score to the agreed ARGUS risk bands."""
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError("Risk score must be finite and between 0 and 100.")

    for upper_bound, label in RISK_BANDS:
        if score <= upper_bound:
            return label

    raise ValueError("Invalid risk score.")


def calculate_risk(
    behavioral_deviation_score: float | None,
    peer_deviation_score: float | None,
    context_risk_score: float | None = None,
    behavioral_explanation: str | None = None,
    peer_explanation: str | None = None,
    context_explanation: str | None = None,
) -> dict[str, Any]:
    """Fuse available evidence scores into one provisional risk score.

    Every supplied score must be finite and in [0, 100].
    Missing scores are excluded and remaining weights are renormalized.
    Equal weights are an initial baseline, not empirically optimized weights.
    """
    candidates = {
        "behavioral_deviation": (
            behavioral_deviation_score,
            behavioral_explanation,
        ),
        "peer_deviation": (
            peer_deviation_score,
            peer_explanation,
        ),
        "context": (
            context_risk_score,
            context_explanation,
        ),
    }

    available = {}

    for name, (value, explanation) in candidates.items():
        if value is None:
            continue

        value = float(value)

        if not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError(
                f"{name} score must be finite and between 0 and 100."
            )

        available[name] = {
            "score": value,
            "explanation": explanation,
        }

    if not available:
        return {
            "risk_score": None,
            "risk_level": "UNAVAILABLE",
            "status": "insufficient_evidence",
            "components_used": [],
            "explanation": (
                "Risk score unavailable because no valid evidence scores "
                "were supplied."
            ),
        }

    # Equal-weight fusion over available evidence components.
    score = sum(
        item["score"] for item in available.values()
    ) / len(available)

    score = round(min(100.0, max(0.0, score)), 2)

    evidence = []
    for name, item in available.items():
        if item["explanation"]:
            evidence.append(
                f"{name}: {item['explanation']}"
            )

    explanation = (
        "Provisional risk indicator calculated by equal-weight fusion "
        f"of {len(available)} available evidence component(s). "
        "This score indicates anomalous behavior, not confirmed "
        "malicious intent."
    )

    if evidence:
        explanation += " Evidence: " + "; ".join(evidence)

    return {
        "risk_score": score,
        "risk_level": get_risk_level(score),
        "status": "scored",
        "components_used": list(available.keys()),
        "explanation": explanation,
    }
