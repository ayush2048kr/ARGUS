
"""Validate the ARGUS behavioral + peer + risk scoring pipeline.

Run from the repository root:
    python -m ml.integration.validate_risk_pipeline

Peer deviation is user-profile-level, not daily.
Context scoring is omitted until supported by actual contextual evidence.
"""

from pathlib import Path

import pandas as pd

from ml.deviation.behavioral_deviation import (
    calculate_behavioral_deviation,
)
from ml.integration.m1_to_m2 import load_m1_features
from ml.risk.risk_engine import calculate_risk


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "ml" / "evaluation" / "output"

PEER_FILE = OUTPUT_DIR / "peer_deviation_user_profiles.csv"
OUTPUT_FILE = OUTPUT_DIR / "argus_risk_pipeline_daily.csv"
SUMMARY_FILE = OUTPUT_DIR / "argus_risk_pipeline_summary.csv"


def main():
    print("Loading integrated M1 features...")
    history = load_m1_features()

    required = {
        "user_id",
        "date",
        "has_sufficient_history",
        "self_activity_drift_zscore",
    }
    missing = required - set(history.columns)

    if missing:
        raise ValueError(
            "Integrated features are missing required columns: "
            + ", ".join(sorted(missing))
        )

    print("Calculating behavioral deviation...")
    behavioral = calculate_behavioral_deviation(history)

    print("Loading saved peer-deviation results...")
    if not PEER_FILE.exists():
        raise FileNotFoundError(
            f"Peer-deviation CSV not found: {PEER_FILE}\n"
            "Generate peer_deviation_user_profiles.csv first."
        )

    peers = pd.read_csv(PEER_FILE)

    peer_required = {
        "user_id",
        "peer_deviation_score",
        "peer_deviation_status",
        "peer_deviation_explanation",
    }
    missing = peer_required - set(peers.columns)

    if missing:
        raise ValueError(
            "Peer results are missing required columns: "
            + ", ".join(sorted(missing))
        )

    if peers["user_id"].duplicated().any():
        raise ValueError("Peer results contain duplicate user IDs.")

    # Peer scores describe full-period user profiles.
    # They are not recalculated for each date.
    peer_columns = [
        "user_id",
        "peer_deviation_score",
        "peer_deviation_status",
        "peer_deviation_explanation",
    ]

    combined = behavioral.merge(
        peers[peer_columns],
        on="user_id",
        how="left",
        validate="many_to_one",
        indicator=True,
    )

    unmatched_users = int((combined["_merge"] != "both").sum())

    if unmatched_users:
        raise ValueError(
            f"{unmatched_users} daily rows have no matching peer profile. "
            "Resolve the user-ID mismatch before scoring."
        )

    combined = combined.drop(columns="_merge")

    # Do not use a peer score marked unavailable.
    combined.loc[
        combined["peer_deviation_status"] != "available",
        "peer_deviation_score",
    ] = float("nan")

    print(f"Daily rows to score: {len(combined):,}")
    print("Calculating provisional risk scores...")

    output_records = []

    for row in combined[
        [
            "user_id",
            "date",
            "behavioral_deviation_score",
            "baseline_status",
            "deviation_explanation",
            "peer_deviation_score",
            "peer_deviation_status",
            "peer_deviation_explanation",
        ]
    ].itertuples(index=False, name=None):

        (
            user_id,
            date,
            behavioral_score,
            baseline_status,
            behavioral_explanation,
            peer_score,
            peer_status,
            peer_explanation,
        ) = row

        # pandas NaN is not None; convert unavailable scores explicitly.
        if pd.isna(behavioral_score):
            behavioral_score = None

        if pd.isna(peer_score):
            peer_score = None

        result = calculate_risk(
            behavioral_deviation_score=behavioral_score,
            peer_deviation_score=peer_score,
            context_risk_score=None,
            behavioral_explanation=(
                behavioral_explanation
                if behavioral_score is not None
                else f"Behavioral score unavailable: {baseline_status}."
            ),
            peer_explanation=(
                peer_explanation
                if peer_score is not None
                else f"Peer score unavailable: {peer_status}."
            ),
            context_explanation=None,
        )

        output_records.append(
            {
                "user_id": user_id,
                "date": pd.Timestamp(date).date().isoformat(),
                "behavioral_deviation_score": behavioral_score,
                "baseline_status": baseline_status,
                "peer_deviation_score": peer_score,
                "peer_deviation_status": peer_status,
                "risk_score": result["risk_score"],
                "risk_level": result["risk_level"],
                "risk_status": result["status"],
                "components_used": ", ".join(
                    result["components_used"]
                ),
                "risk_explanation": result["explanation"],
                "peer_score_scope": "full_period_user_profile",
                "context_score_status": "not_implemented",
            }
        )

    results = pd.DataFrame(output_records)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUTPUT_FILE, index=False)

    print("\n--- PIPELINE VALIDATION ---")
    print("Daily rows:", len(results))
    print("Unique users:", results["user_id"].nunique())
    print(
        "Duplicate user/date rows:",
        results.duplicated(["user_id", "date"]).sum(),
    )
    print("Missing risk scores:", results["risk_score"].isna().sum())
    print(
        "Rows with only one score component:",
        results["components_used"].map(
            lambda value: len(value.split(", ")) if value else 0
        ).eq(1).sum(),
    )

    print("\nRisk-level distribution:")
    print(
        results["risk_level"]
        .value_counts(dropna=False)
        .to_string()
    )

    print("\nBehavioral baseline statuses:")
    print(
        results["baseline_status"]
        .value_counts(dropna=False)
        .to_string()
    )

    print("\nRisk score summary:")
    print(results["risk_score"].describe().to_string())

    summary = (
        results.groupby(
            ["risk_level", "risk_status"],
            dropna=False,
        )
        .size()
        .rename("row_count")
        .reset_index()
    )
    summary.to_csv(SUMMARY_FILE, index=False)

    print("\nTop 10 provisional scores:")
    columns = [
        "user_id",
        "date",
        "behavioral_deviation_score",
        "peer_deviation_score",
        "risk_score",
        "risk_level",
        "components_used",
    ]
    print(
        results.sort_values(
            "risk_score",
            ascending=False,
            na_position="last",
        )[columns]
        .head(10)
        .to_string(index=False)
    )

    print("\nSaved daily results:", OUTPUT_FILE)
    print("Saved summary:", SUMMARY_FILE)
    print(
        "\nNOTE: These are provisional anomaly-risk indicators, "
        "not verified threat detections or accuracy measurements."
    )
    print(
        "Peer scores are full-period profile scores. "
        "Context scoring has not yet been implemented."
    )


if __name__ == "__main__":
    main()
