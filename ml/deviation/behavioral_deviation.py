
"""Historical behavioral deviation scoring for ARGUS.

This module measures deviation from a user's own historical activity.
It does not calculate the authoritative ARGUS risk score.
"""

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = [
    "user_id",
    "date",
    "has_sufficient_history",
    "self_activity_drift_zscore",
]


def calculate_behavioral_deviation(
    history: pd.DataFrame,
    saturation_z: float = 4.0,
) -> pd.DataFrame:
    """Calculate a bounded behavioral deviation score.

    Parameters
    ----------
    history:
        Stage 2 history data containing one row per user/date.
    saturation_z:
        Absolute z-score that maps to 100. This is an initial,
        configurable scale, not an empirically optimized threshold.

    Returns
    -------
    pd.DataFrame
        Original columns plus absolute z-score, deviation score,
        baseline status, and an explanation.
    """
    if history.empty:
        raise ValueError("History DataFrame is empty.")

    if not np.isfinite(saturation_z) or saturation_z <= 0:
        raise ValueError("saturation_z must be finite and positive.")

    missing = [
        column for column in REQUIRED_COLUMNS
        if column not in history.columns
    ]
    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(missing)
        )

    df = history.copy()

    if df[["user_id", "date"]].isna().any().any():
        raise ValueError("user_id and date cannot contain null values.")

    if df.duplicated(["user_id", "date"]).any():
        raise ValueError("Duplicate user/date records found.")

    df["date"] = pd.to_datetime(df["date"], errors="raise")

    # Parse sufficiency explicitly; never rely on bool("False").
    flag_map = {
        True: True,
        False: False,
        1: True,
        0: False,
        "true": True,
        "false": False,
        "1": True,
        "0": False,
    }

    def parse_flag(value):
        if pd.isna(value):
            raise ValueError("History sufficiency flag cannot be null.")
        key = value.strip().lower() if isinstance(value, str) else value
        if key not in flag_map:
            raise ValueError(
                f"Invalid history sufficiency flag: {value!r}"
            )
        return flag_map[key]

    df["has_sufficient_history"] = (
        df["has_sufficient_history"].map(parse_flag).astype(bool)
    )

    z = pd.to_numeric(
        df["self_activity_drift_zscore"],
        errors="raise",
    ).astype(float)

    if np.isinf(z.to_numpy()).any():
        raise ValueError("Z-scores cannot contain infinity.")

    # A usable baseline requires sufficient history and a valid z-score.
    sufficient = df["has_sufficient_history"]
    usable_z = z.notna()
    available = sufficient & usable_z

    df["absolute_activity_zscore"] = z.abs()

    # Initial transparent mapping: |z| >= saturation_z maps to 100.
    df["behavioral_deviation_score"] = np.nan
    df.loc[available, "behavioral_deviation_score"] = (
        (z.loc[available].abs() / saturation_z)
        .clip(lower=0.0, upper=1.0)
        .mul(100.0)
    )

    df["baseline_status"] = np.select(
        [
            ~sufficient,
            sufficient & ~usable_z,
        ],
        [
            "insufficient_history",
            "zscore_unavailable",
        ],
        default="available",
    )

    df["deviation_explanation"] = np.select(
        [
            ~sufficient,
            sufficient & ~usable_z,
            available & (z.abs() >= saturation_z),
            available & (z.abs() >= 2.0),
        ],
        [
            "Insufficient historical observations; deviation not scored.",
            "History sufficiency passed, but the z-score is unavailable.",
            "Activity differs from the historical mean by at least "
            f"{saturation_z:g} standard deviations.",
            "Activity differs from the historical mean by at least "
            "2 standard deviations.",
        ],
        default="No deviation of at least 2 standard deviations detected.",
    )

    return df
