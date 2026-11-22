
"""LDAP-derived peer context for ARGUS.

Compares each user's behavioral deviation score with other users sharing
the same LDAP role and domain on the same date.

The context score measures peer-relative unusualness, not malicious intent.
Role/domain membership alone never increases risk.
"""

import numpy as np
import pandas as pd


MIN_CONTEXT_PEERS = 5
MIN_PEER_SCORE_STD = 1e-9


def calculate_ldap_context(
    daily_behavior: pd.DataFrame,
    min_context_peers: int = MIN_CONTEXT_PEERS,
) -> pd.DataFrame:
    """Calculate context-relative behavioral deviation.

    Required columns:
        user_id, date, behavioral_deviation_score, role, ldap_domain

    Returns one row per input row with:
        context_risk_score, context_status, context_explanation,
        context_peer_count
    """
    required = {
        "user_id",
        "date",
        "behavioral_deviation_score",
        "role",
        "ldap_domain",
    }
    missing = required - set(daily_behavior.columns)
    if missing:
        raise ValueError(
            "LDAP context input is missing columns: "
            + ", ".join(sorted(missing))
        )

    if daily_behavior.empty:
        raise ValueError("LDAP context input is empty.")

    if min_context_peers < 2:
        raise ValueError("min_context_peers must be at least 2.")

    # Reset the index so row updates remain unambiguous even when the
    # caller supplies a DataFrame with duplicated index labels.
    data = daily_behavior.copy().reset_index(drop=True)
    data["_row_id"] = np.arange(len(data))

    data["date"] = pd.to_datetime(data["date"], errors="raise")
    data["behavioral_deviation_score"] = pd.to_numeric(
        data["behavioral_deviation_score"], errors="coerce"
    )

    if data[["user_id", "date"]].isna().any().any():
        raise ValueError("Context input contains missing user/date keys.")

    if data.duplicated(["user_id", "date"]).any():
        raise ValueError("Context input has duplicate user/date rows.")

    # Treat blank LDAP attributes as unavailable, not as real peer groups.
    for column in ("role", "ldap_domain"):
        data[column] = data[column].astype("string").str.strip()
        data.loc[data[column].eq(""), column] = pd.NA

    data["context_group"] = (
        data["role"].fillna("UNKNOWN_ROLE")
        + "|"
        + data["ldap_domain"].fillna("UNKNOWN_DOMAIN")
    )

    data["context_risk_score"] = np.nan
    data["context_status"] = "context_unavailable"
    data["context_explanation"] = (
        "Context score unavailable because comparable evidence "
        "is insufficient. No conclusion about malicious intent can be drawn."
    )
    data["context_peer_count"] = 0

    # Compare users only with other users in the same role/domain group
    # on the same date.
    for _, date_group in data.groupby("date", sort=False):
        for _, group in date_group.groupby(
            "context_group", dropna=False, sort=False
        ):
            valid_group = group[
                group["role"].notna() & group["ldap_domain"].notna()
            ]

            if valid_group.empty:
                continue

            for index, row in valid_group.iterrows():
                score = row["behavioral_deviation_score"]

                peers = valid_group[
                    valid_group["user_id"] != row["user_id"]
                ]

                peer_count = int(peers["user_id"].nunique())
                data.at[index, "context_peer_count"] = peer_count

                if pd.isna(score) or not np.isfinite(score):
                    data.at[index, "context_status"] = (
                        "behavioral_evidence_unavailable"
                    )
                    data.at[index, "context_explanation"] = (
                        "LDAP peer context exists, but the user's "
                        "behavioral deviation score is unavailable or "
                        "non-finite."
                    )
                    continue

                if peer_count < min_context_peers:
                    data.at[index, "context_status"] = (
                        "insufficient_context_peers"
                    )
                    data.at[index, "context_explanation"] = (
                        f"Only {peer_count} comparable role/domain peers; "
                        f"at least {min_context_peers} are required."
                    )
                    continue

                peer_scores = peers["behavioral_deviation_score"]
                peer_scores = peer_scores[
                    np.isfinite(peer_scores)
                ]

                if len(peer_scores) < min_context_peers:
                    data.at[index, "context_status"] = (
                        "insufficient_scored_peers"
                    )
                    data.at[index, "context_explanation"] = (
                        f"Only {len(peer_scores)} comparable peers have "
                        "finite behavioral deviation scores; "
                        f"at least {min_context_peers} are required."
                    )
                    continue

                mean = float(peer_scores.mean())
                std = float(peer_scores.std(ddof=1))
                delta = float(score - mean)

                if not all(np.isfinite(value) for value in (mean, std, delta)):
                    data.at[index, "context_status"] = (
                        "behavioral_evidence_unavailable"
                    )
                    data.at[index, "context_explanation"] = (
                        "Context comparison could not be calculated from "
                        "finite behavioral evidence."
                    )
                    continue

                if std < MIN_PEER_SCORE_STD:
                    if abs(delta) < MIN_PEER_SCORE_STD:
                        context_score = 0.0
                        scoring_basis = (
                            "peer scores have effectively zero variance "
                            "and the user's score matches the peer mean"
                        )
                    else:
                        context_score = 100.0
                        scoring_basis = (
                            "peer scores have effectively zero variance "
                            "but the user's score differs from the peer mean"
                        )
                else:
                    absolute_z = abs(delta) / std
                    context_score = min(absolute_z / 3.0, 1.0) * 100.0
                    scoring_basis = (
                        f"absolute peer-standardized deviation is "
                        f"{absolute_z:.2f} standard deviations"
                    )

                if delta > 0:
                    direction = "above"
                elif delta < 0:
                    direction = "below"
                else:
                    direction = "equal to"

                data.at[index, "context_risk_score"] = round(
                    float(context_score), 2
                )
                data.at[index, "context_status"] = "scored"
                data.at[index, "context_explanation"] = (
                    f"Peer-relative unusualness score: {context_score:.2f}/100. "
                    f"The user's behavioral deviation ({score:.2f}) is "
                    f"{abs(delta):.2f} points {direction} the role/domain "
                    f"peer mean ({mean:.2f}; peer standard deviation "
                    f"{std:.4f}). {scoring_basis}. "
                    f"Comparison uses {len(peer_scores)} scored peers "
                    f"from {peer_count} comparable users. "
                    "This score measures unusualness in either direction; "
                    "it does not establish malicious intent."
                )

    return (
        data.sort_values("_row_id")[
            [
                "user_id",
                "date",
                "context_risk_score",
                "context_status",
                "context_explanation",
                "context_peer_count",
            ]
        ]
        .reset_index(drop=True)
    )
