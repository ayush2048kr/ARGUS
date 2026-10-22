
"""Run and validate ARGUS behavioral, peer, and LDAP context pipeline.

Run from the repository root:
    python -m ml.integration.validate_risk_pipeline

LDAP role/domain define comparable context groups. Membership alone does
not increase risk. Context scoring requires sufficient same-date peer
evidence and remains a provisional anomaly indicator.
"""

from pathlib import Path

import pandas as pd

from ml.context.ldap_context_engine import calculate_ldap_context
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

CONTEXT_COLUMNS = [
    "role",
    "ldap_domain",
    "context_event_count",
    "context_match_status",
]


def _require_columns(
    df: pd.DataFrame,
    required: set[str],
    name: str,
) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{name} is missing columns: "
            + ", ".join(sorted(missing))
        )


def main():
    print("Loading integrated M1 features and LDAP context...")
    history = load_m1_features().copy()

    required = {
        "user_id",
        "date",
        "has_sufficient_history",
        "self_activity_drift_zscore",
        *CONTEXT_COLUMNS,
    }
    _require_columns(history, required, "Integrated M1 features")

    if history.duplicated(["user_id", "date"]).any():
        raise ValueError(
            "Integrated features contain duplicate user/date rows."
        )

    history["date"] = pd.to_datetime(history["date"], errors="raise")
    expected_rows = len(history)

    print("Calculating behavioral deviation...")
    behavioral = calculate_behavioral_deviation(history).copy()

    _require_columns(
        behavioral,
        {
            "user_id",
            "date",
            "behavioral_deviation_score",
            "baseline_status",
            "deviation_explanation",
        },
        "Behavioral deviation output",
    )

    behavioral["date"] = pd.to_datetime(
        behavioral["date"], errors="raise"
    )

    if behavioral.duplicated(["user_id", "date"]).any():
        raise ValueError(
            "Behavioral deviation output contains duplicate user/date rows."
        )

    # Use history as the single authoritative source for LDAP attributes.
    # Drop any context fields returned by behavioral scoring first, so
    # pandas cannot silently rename them to role_x/role_y, etc.
    behavioral = behavioral.drop(
        columns=[
            column
            for column in CONTEXT_COLUMNS
            if column in behavioral.columns
        ]
    )

    combined = behavioral.merge(
        history[
            ["user_id", "date", *CONTEXT_COLUMNS]
        ],
        on=["user_id", "date"],
        how="left",
        validate="one_to_one",
        indicator="_history_merge",
    )

    if len(combined) != expected_rows:
        raise ValueError(
            "Behavioral/context integration changed the daily row count."
        )

    if (combined["_history_merge"] != "both").any():
        raise ValueError(
            "Some behavioral rows could not be matched to integrated "
            "daily features."
        )

    combined = combined.drop(columns="_history_merge")

    _require_columns(
        combined,
        set(CONTEXT_COLUMNS),
        "Behavioral output joined with LDAP context",
    )

    print("Calculating LDAP role/domain context deviation...")
    ldap_context = calculate_ldap_context(
        combined[
            [
                "user_id",
                "date",
                "behavioral_deviation_score",
                "role",
                "ldap_domain",
            ]
        ].copy()
    )

    _require_columns(
        ldap_context,
        {
            "user_id",
            "date",
            "context_risk_score",
            "context_status",
            "context_explanation",
            "context_peer_count",
        },
        "LDAP context output",
    )

    if ldap_context.duplicated(["user_id", "date"]).any():
        raise ValueError(
            "LDAP context output contains duplicate user/date rows."
        )

    combined = combined.merge(
        ldap_context,
        on=["user_id", "date"],
        how="left",
        validate="one_to_one",
        indicator="_ldap_context_merge",
    )

    if len(combined) != expected_rows:
        raise ValueError(
            "LDAP context integration changed the daily row count."
        )

    if (combined["_ldap_context_merge"] != "both").any():
        raise ValueError(
            "Some daily rows could not be matched to LDAP context output."
        )

    combined = combined.drop(columns="_ldap_context_merge")

    print("Loading saved peer-deviation results...")
    if not PEER_FILE.exists():
        raise FileNotFoundError(
            f"Peer-deviation CSV not found: {PEER_FILE}\n"
            "Generate peer_deviation_user_profiles.csv first."
        )

    peers = pd.read_csv(PEER_FILE)

    _require_columns(
        peers,
        {
            "user_id",
            "peer_deviation_score",
            "peer_deviation_status",
            "peer_deviation_explanation",
        },
        "Peer results",
    )

    if peers["user_id"].isna().any():
        raise ValueError("Peer results contain missing user IDs.")

    if peers["user_id"].duplicated().any():
        raise ValueError("Peer results contain duplicate user IDs.")

    combined = combined.merge(
        peers[
            [
                "user_id",
                "peer_deviation_score",
                "peer_deviation_status",
                "peer_deviation_explanation",
            ]
        ],
        on="user_id",
        how="left",
        validate="many_to_one",
        indicator="_peer_merge",
    )

    unmatched = int((combined["_peer_merge"] != "both").sum())
    if unmatched:
        raise ValueError(
            f"{unmatched} daily rows have no matching peer profile. "
            "Resolve the user-ID mismatch before scoring."
        )

    combined = combined.drop(columns="_peer_merge")

    combined.loc[
        combined["peer_deviation_status"] != "available",
        "peer_deviation_score",
    ] = float("nan")

    print(f"Daily rows to score: {len(combined):,}")

    output_records = []
    scoring_columns = [
        "user_id",
        "date",
        "behavioral_deviation_score",
        "baseline_status",
        "deviation_explanation",
        "peer_deviation_score",
        "peer_deviation_status",
        "peer_deviation_explanation",
        *CONTEXT_COLUMNS,
        "context_risk_score",
        "context_status",
        "context_explanation",
        "context_peer_count",
    ]

    for row in combined[scoring_columns].itertuples(
        index=False, name=None
    ):
        (
            user_id,
            date,
            behavioral_score,
            baseline_status,
            behavioral_explanation,
            peer_score,
            peer_status,
            peer_explanation,
            role,
            ldap_domain,
            context_event_count,
            context_match_status,
            context_score,
            context_status,
            context_explanation,
            context_peer_count,
        ) = row

        if pd.isna(behavioral_score):
            behavioral_score = None
        if pd.isna(peer_score):
            peer_score = None
        if pd.isna(context_score):
            context_score = None
        if pd.isna(role):
            role = None
        if pd.isna(ldap_domain):
            ldap_domain = None
        if pd.isna(context_event_count):
            context_event_count = None
        if pd.isna(context_peer_count):
            context_peer_count = 0

        result = calculate_risk(
            behavioral_deviation_score=behavioral_score,
            peer_deviation_score=peer_score,
            context_risk_score=context_score,
            behavioral_explanation=(
                str(behavioral_explanation)
                if behavioral_score is not None
                else f"Behavioral score unavailable: {baseline_status}."
            ),
            peer_explanation=(
                str(peer_explanation)
                if peer_score is not None
                else f"Peer score unavailable: {peer_status}."
            ),
            context_explanation=str(context_explanation),
        )

        output_records.append(
            {
                "user_id": user_id,
                "date": pd.Timestamp(date).date().isoformat(),
                "behavioral_deviation_score": behavioral_score,
                "baseline_status": baseline_status,
                "peer_deviation_score": peer_score,
                "peer_deviation_status": peer_status,
                "role": role,
                "ldap_domain": ldap_domain,
                "context_event_count": context_event_count,
                "context_match_status": context_match_status,
                "context_risk_score": context_score,
                "context_status": context_status,
                "context_explanation": context_explanation,
                "context_peer_count": int(context_peer_count),
                "risk_score": result["risk_score"],
                "risk_level": result["risk_level"],
                "risk_status": result["status"],
                "components_used": ", ".join(
                    result["components_used"]
                ),
                "risk_explanation": result["explanation"],
                "peer_score_scope": "full_period_user_profile",
            }
        )

    results = pd.DataFrame(output_records)

    if len(results) != expected_rows:
        raise ValueError(
            "Final risk output does not preserve the integrated daily rows."
        )

    if results.duplicated(["user_id", "date"]).any():
        raise ValueError("Final results contain duplicate user/date rows.")

    for column in (
        "behavioral_deviation_score",
        "peer_deviation_score",
        "context_risk_score",
        "risk_score",
    ):
        numeric = pd.to_numeric(results[column], errors="coerce")
        if not numeric.dropna().between(0, 100).all():
            raise ValueError(
                f"{column} contains scores outside the 0-100 range."
            )

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
    print("Rows with role:", results["role"].notna().sum())
    print("Rows with LDAP domain:", results["ldap_domain"].notna().sum())
    print(
        "Rows with numeric context scores:",
        results["context_risk_score"].notna().sum(),
    )

    print("\nLDAP join status:")
    print(
        results["context_match_status"]
        .value_counts(dropna=False)
        .to_string()
    )

    print("\nContext scoring status:")
    print(
        results["context_status"]
        .value_counts(dropna=False)
        .to_string()
    )

    print("\nRisk-level distribution:")
    print(results["risk_level"].value_counts(dropna=False).to_string())

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

    print("\nSaved daily results:", OUTPUT_FILE)
    print("Saved summary:", SUMMARY_FILE)
    print(
        "\nNOTE: Scores are provisional anomaly-risk indicators, not "
        "probabilities of maliciousness. LDAP role/domain only define "
        "comparable peer context; membership alone does not increase risk."
    )


if __name__ == "__main__":
    main()
