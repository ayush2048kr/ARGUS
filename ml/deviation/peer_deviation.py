
"""Peer-group behavioral deviation for ARGUS."""

import numpy as np
import pandas as pd

from ml.features.user_profile import PROFILE_FEATURES


def calculate_peer_deviation(
    user_profiles: pd.DataFrame,
    cluster_assignments: pd.DataFrame,
    feature_columns: list[str] | None = None,
    saturation_z: float = 3.0,
    min_peers: int = 5,
) -> pd.DataFrame:
    """Compare each user's profile with other users in their cluster.

    This measures peer-relative behavioral differences, not maliciousness.
    The supplied profiles and assignments must use the same feature
    definitions and compatible training/evaluation period.
    """
    if user_profiles.empty:
        raise ValueError("User profiles are empty.")

    if cluster_assignments.empty:
        raise ValueError("Cluster assignments are empty.")

    if not np.isfinite(saturation_z) or saturation_z <= 0:
        raise ValueError("saturation_z must be finite and positive.")

    if min_peers < 2:
        raise ValueError("min_peers must be at least 2.")

    if feature_columns is None:
        feature_columns = PROFILE_FEATURES

    feature_columns = list(feature_columns)

    if not feature_columns:
        raise ValueError("At least one feature is required.")

    profile_required = ["user_id"] + feature_columns
    assignment_required = ["user_id", "cluster_id"]

    for name, frame, required in [
        ("User profiles", user_profiles, profile_required),
        ("Cluster assignments", cluster_assignments, assignment_required),
    ]:
        missing = [c for c in required if c not in frame.columns]
        if missing:
            raise ValueError(
                f"{name} missing columns: {', '.join(missing)}"
            )

        if frame["user_id"].isna().any():
            raise ValueError(f"{name} contain null user IDs.")

        if frame["user_id"].duplicated().any():
            raise ValueError(f"{name} contain duplicate user IDs.")

    profiles = user_profiles[profile_required].copy()
    assignments = cluster_assignments[assignment_required].copy()

    profiles[feature_columns] = profiles[feature_columns].apply(
        pd.to_numeric, errors="raise"
    )

    values = profiles[feature_columns].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Profile features must be finite and non-null.")

    if assignments["cluster_id"].isna().any():
        raise ValueError("Cluster assignments cannot be null.")

    merged = profiles.merge(
        assignments,
        on="user_id",
        how="outer",
        validate="one_to_one",
        indicator=True,
    )

    unmatched = merged["_merge"] != "both"
    if unmatched.any():
        raise ValueError(
            f"Profile/assignment user mismatch: {int(unmatched.sum())} rows."
        )

    merged = merged.drop(columns="_merge")

    results = []

    for cluster_id, group in merged.groupby("cluster_id", sort=False):
        group = group.reset_index(drop=True)
        cluster_values = group[feature_columns].to_numpy(dtype=float)
        cluster_size = len(group)

        for i, row in group.iterrows():
            peer_count = cluster_size - 1

            result = {
                "user_id": row["user_id"],
                "cluster_id": cluster_id,
                "peer_count": peer_count,
                "peer_deviation_score": np.nan,
                "peer_deviation_status": "available",
                "peer_deviation_explanation": "",
            }

            if peer_count < min_peers:
                result["peer_deviation_status"] = "insufficient_peers"
                result["peer_deviation_explanation"] = (
                    f"Only {peer_count} peers available; "
                    f"at least {min_peers} required."
                )
                results.append(result)
                continue

            peer_values = np.delete(cluster_values, i, axis=0)
            user_values = cluster_values[i]

            peer_means = peer_values.mean(axis=0)
            peer_stds = peer_values.std(axis=0, ddof=1)

            deviations = np.zeros(len(feature_columns), dtype=float)

            for j, (value, mean, std) in enumerate(
                zip(user_values, peer_means, peer_stds)
            ):
                delta = value - mean

                if std < 1e-12:
                    # If peers have no variation, avoid division by zero.
                    deviations[j] = (
                        0.0 if abs(delta) < 1e-12
                        else np.sign(delta) * saturation_z
                    )
                else:
                    deviations[j] = delta / std

            # Cap individual feature contributions before aggregation.
            absolute = np.abs(deviations)
            capped = np.clip(absolute, 0.0, saturation_z)

            result["peer_deviation_score"] = float(
                capped.mean() / saturation_z * 100.0
            )

            top_indices = np.argsort(absolute)[::-1][:3]
            explanations = []

            for j in top_indices:
                if absolute[j] < 1.0:
                    continue

                direction = "above" if deviations[j] > 0 else "below"
                explanations.append(
                    f"{feature_columns[j]} {direction} peers "
                    f"({deviations[j]:+.2f} peer SD)"
                )

            result["peer_deviation_explanation"] = (
                "; ".join(explanations)
                if explanations
                else "No feature differs from peers by at least one "
                     "peer standard deviation."
            )

            results.append(result)

    return pd.DataFrame(results)
