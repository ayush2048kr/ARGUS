
"""Integrate M1 daily features and monthly LDAP context for M2."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

STAGE1_PATH = (
    PROJECT_ROOT / "data" / "processed"
    / "user_features_stage1_daily.csv"
)
STAGE2_PATH = (
    PROJECT_ROOT / "data" / "processed"
    / "user_features_stage2_history.csv"
)
CONTEXT_PATH = (
    PROJECT_ROOT / "data" / "processed"
    / "user_month_context.csv"
)

JOIN_COLUMNS = ["user_id", "date"]
CONTEXT_KEY = ["user_id", "month"]

CONTEXT_OUTPUT_COLUMNS = [
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
            f"{name} is missing required columns: "
            + ", ".join(sorted(missing))
        )


def _load_context() -> pd.DataFrame:
    """Load monthly context, or return an explicit unavailable result."""
    columns = CONTEXT_KEY + CONTEXT_OUTPUT_COLUMNS

    if not CONTEXT_PATH.exists():
        print(
            f"WARNING: LDAP context file not found: {CONTEXT_PATH}. "
            "Continuing without context."
        )
        return pd.DataFrame(
            columns=columns
        )

    context = pd.read_csv(
        CONTEXT_PATH,
        dtype={
            "user_id": "string",
            "month": "string",
            "role": "string",
            "ldap_domain": "string",
        },
    )

    _require_columns(
        context,
        {"user_id", "month", "role", "ldap_domain"},
        "M1 monthly context",
    )

    context["user_id"] = context["user_id"].str.strip()
    context["month"] = context["month"].str.strip()

    if context["user_id"].isna().any() or context["user_id"].eq("").any():
        raise ValueError("M1 context contains blank user IDs.")

    valid_month = context["month"].str.fullmatch(
        r"\d{4}-(0[1-9]|1[0-2])",
        na=False,
    )
    if not valid_month.all():
        raise ValueError(
            "M1 context month must use valid YYYY-MM values."
        )

    duplicate = context.duplicated(CONTEXT_KEY, keep=False)
    if duplicate.any():
        examples = context.loc[
            duplicate, CONTEXT_KEY
        ].head(10).to_dict("records")
        raise ValueError(
            "M1 context has duplicate user/month keys. "
            f"Examples: {examples}"
        )

    for column in ("role", "ldap_domain"):
        context[column] = context[column].replace(
            r"^\s*$", pd.NA, regex=True
        )

    if "event_count" in context.columns:
        context = context.rename(
            columns={"event_count": "context_event_count"}
        )
    else:
        context["context_event_count"] = pd.NA

    # A row in user_month_context means M1 found a monthly context match.
    # Attribute values may still be absent, which is tracked separately.
    context["context_match_status"] = "CONTEXT_MATCHED"
    no_attributes = (
        context["role"].isna() & context["ldap_domain"].isna()
    )
    context.loc[
        no_attributes, "context_match_status"
    ] = "CONTEXT_MATCHED_NO_ATTRIBUTES"

    return context[columns]


def load_m1_features() -> pd.DataFrame:
    """
    Load Stage 1 and Stage 2 features, then attach monthly LDAP context.

    Missing context does not drop rows and is not itself a risk indicator.
    """
    if not STAGE1_PATH.exists():
        raise FileNotFoundError(f"Stage 1 file not found: {STAGE1_PATH}")
    if not STAGE2_PATH.exists():
        raise FileNotFoundError(f"Stage 2 file not found: {STAGE2_PATH}")

    stage1 = pd.read_csv(STAGE1_PATH)
    stage2 = pd.read_csv(STAGE2_PATH)

    for name, df in (("Stage 1", stage1), ("Stage 2", stage2)):
        _require_columns(df, set(JOIN_COLUMNS), name)
        df["user_id"] = df["user_id"].astype("string").str.strip()
        df["date"] = pd.to_datetime(df["date"], errors="raise")

        if df["user_id"].isna().any() or df["user_id"].eq("").any():
            raise ValueError(f"{name} contains blank user IDs.")
        if df.duplicated(JOIN_COLUMNS).any():
            raise ValueError(
                f"{name} contains duplicate user/date records."
            )

    integrated = stage1.merge(
        stage2,
        on=JOIN_COLUMNS,
        how="inner",
        suffixes=("_stage1", "_stage2"),
        validate="one_to_one",
    )

    # Preserve the existing strict Stage 1/Stage 2 completeness contract.
    if len(integrated) != len(stage1) or len(integrated) != len(stage2):
        raise ValueError(
            "Stage 1/Stage 2 integration lost records. "
            f"Stage 1={len(stage1)}, Stage 2={len(stage2)}, "
            f"integrated={len(integrated)}."
        )

    context = _load_context()
    integrated["month"] = integrated["date"].dt.strftime("%Y-%m")

    if context.empty:
        integrated["role"] = pd.NA
        integrated["ldap_domain"] = pd.NA
        integrated["context_event_count"] = pd.NA
        integrated["context_match_status"] = (
            "CONTEXT_FILE_MISSING"
            if not CONTEXT_PATH.exists()
            else "NO_CONTEXT_FOR_USER_MONTH"
        )
    else:
        before = len(integrated)

        integrated = integrated.merge(
            context,
            on=CONTEXT_KEY,
            how="left",
            validate="many_to_one",
        )

        if len(integrated) != before:
            raise ValueError(
                "LDAP context join changed the number of daily rows."
            )

        integrated["context_match_status"] = (
            integrated["context_match_status"].fillna(
                "NO_CONTEXT_FOR_USER_MONTH"
            )
        )

    print("M1 -> M2 integration successful")
    print(f"Stage 1 rows       : {len(stage1):,}")
    print(f"Stage 2 rows       : {len(stage2):,}")
    print(f"Integrated rows    : {len(integrated):,}")
    print(f"Unique users       : {integrated['user_id'].nunique():,}")
    print(
        "Context status:\n"
        + integrated["context_match_status"]
        .value_counts(dropna=False)
        .to_string()
    )

    return integrated


if __name__ == "__main__":
    df = load_m1_features()
    print(f"Columns: {len(df.columns)}")
    print(
        f"Date range: {df['date'].min().date()} -> "
        f"{df['date'].max().date()}"
    )
