from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

STAGE1_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "user_features_stage1_daily.csv"
)

STAGE2_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "user_features_stage2_history.csv"
)

JOIN_COLUMNS = ["user_id", "date"]


def load_m1_features() -> pd.DataFrame:
    """
    Load and integrate the feature datasets produced by M1.

    M1 owns data processing and feature generation.
    M2 consumes the resulting Stage 1 and Stage 2 features.
    """

    if not STAGE1_PATH.exists():
        raise FileNotFoundError(
            f"Stage 1 file not found: {STAGE1_PATH}"
        )

    if not STAGE2_PATH.exists():
        raise FileNotFoundError(
            f"Stage 2 file not found: {STAGE2_PATH}"
        )

    stage1 = pd.read_csv(STAGE1_PATH)
    stage2 = pd.read_csv(STAGE2_PATH)

    for name, df in [
        ("Stage 1", stage1),
        ("Stage 2", stage2),
    ]:
        missing = [
            column
            for column in JOIN_COLUMNS
            if column not in df.columns
        ]

        if missing:
            raise ValueError(
                f"{name} is missing join columns: {missing}"
            )

    stage1["date"] = pd.to_datetime(
        stage1["date"],
        errors="raise",
    )

    stage2["date"] = pd.to_datetime(
        stage2["date"],
        errors="raise",
    )

    if stage1.duplicated(JOIN_COLUMNS).any():
        raise ValueError(
            "Stage 1 contains duplicate user/date records."
        )

    if stage2.duplicated(JOIN_COLUMNS).any():
        raise ValueError(
            "Stage 2 contains duplicate user/date records."
        )

    integrated = stage1.merge(
        stage2,
        on=JOIN_COLUMNS,
        how="inner",
        suffixes=("_stage1", "_stage2"),
        validate="one_to_one",
    )

    if len(integrated) != len(stage1):
        raise ValueError(
            "Integration lost Stage 1 records."
        )

    if len(integrated) != len(stage2):
        raise ValueError(
            "Integration lost Stage 2 records."
        )

    return integrated


if __name__ == "__main__":
    df = load_m1_features()

    print("M1 -> M2 integration successful")
    print(f"Integrated rows : {len(df):,}")
    print(f"Unique users    : {df['user_id'].nunique():,}")
    print(
        f"Date range      : "
        f"{df['date'].min().date()} -> "
        f"{df['date'].max().date()}"
    )
    print(f"Columns         : {len(df.columns)}")