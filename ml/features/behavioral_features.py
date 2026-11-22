import pandas as pd


REQUIRED_COLUMNS = [
    "event_id",
    "user_id",
    "timestamp",
    "resource",
    "device_id",
]


def extract_behavioral_features(events: pd.DataFrame) -> pd.DataFrame:
    """
    Convert normalized ARGUS event-level data into
    user-level behavioral features.

    Parameters
    ----------
    events : pd.DataFrame
        Normalized ARGUS events following data/schema/event_schema.json.

    Returns
    -------
    pd.DataFrame
        One row per user containing behavioral features.

    Notes
    -----
    Only features supported by the current HTTP dataset
    are extracted. Fields unavailable in the HTTP source
    are not artificially populated.
    """

    # -----------------------------------------------------
    # 1. Validate required input columns
    # -----------------------------------------------------

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in events.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing_columns)
        )

    if events.empty:
        raise ValueError("Input event DataFrame is empty.")

    # -----------------------------------------------------
    # 2. Work on a copy
    # -----------------------------------------------------

    df = events.copy()

    # -----------------------------------------------------
    # 3. Convert timestamp
    # -----------------------------------------------------

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    invalid_timestamps = df["timestamp"].isna().sum()

    if invalid_timestamps > 0:
        raise ValueError(
            f"Found {invalid_timestamps} invalid timestamps."
        )

    # -----------------------------------------------------
    # 4. Temporal fields
    # -----------------------------------------------------

    df["hour_of_day"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek

    df["is_weekend"] = (
        df["day_of_week"] >= 5
    )

    # -----------------------------------------------------
    # 5. Base user-level features
    # -----------------------------------------------------

    features = (
        df.groupby("user_id")
        .agg(
            activity_frequency=("event_id", "count"),
            resource_access_frequency=("resource", "count"),
            unique_resource_count=("resource", "nunique"),
            unique_device_count=("device_id", "nunique"),
        )
        .reset_index()
    )

    # -----------------------------------------------------
    # 6. Weekday / weekend activity
    # -----------------------------------------------------

    weekday_activity = (
        df.loc[~df["is_weekend"]]
        .groupby("user_id")
        .size()
        .rename("weekday_activity")
    )

    weekend_activity = (
        df.loc[df["is_weekend"]]
        .groupby("user_id")
        .size()
        .rename("weekend_activity")
    )

    features = features.merge(
        weekday_activity,
        on="user_id",
        how="left",
    )

    features = features.merge(
        weekend_activity,
        on="user_id",
        how="left",
    )

    features[
        [
            "weekday_activity",
            "weekend_activity",
        ]
    ] = features[
        [
            "weekday_activity",
            "weekend_activity",
        ]
    ].fillna(0)

    # -----------------------------------------------------
    # 7. Hourly activity distribution
    # -----------------------------------------------------

    hourly_activity = pd.crosstab(
        df["user_id"],
        df["hour_of_day"],
    )

    hourly_activity = hourly_activity.reindex(
        columns=range(24),
        fill_value=0,
    )

    hourly_activity.columns = [
        f"hour_{hour}"
        for hour in range(24)
    ]

    hourly_activity = (
        hourly_activity
        .reset_index()
    )

    features = features.merge(
        hourly_activity,
        on="user_id",
        how="left",
    )

    # -----------------------------------------------------
    # 8. Ensure numeric feature columns
    # -----------------------------------------------------

    feature_columns = [
        column
        for column in features.columns
        if column != "user_id"
    ]

    features[feature_columns] = (
        features[feature_columns]
        .apply(pd.to_numeric)
        .fillna(0)
    )

    # -----------------------------------------------------
    # 9. Return user-level feature matrix
    # -----------------------------------------------------

    return features