import pandas as pd


PROFILE_FEATURES = [
    "login_count_1d",
    "logoff_count_1d",
    "usb_connect_count_1d",
    "http_request_count_1d",
    "total_activity_count_1d",
    "distinct_devices_count_1d",
    "off_hours_event_ratio_1d",
    "active_span_hours_1d",
    "cloud_storage_visit_count_1d",
    "file_sharing_visit_count_1d",
    "technology_visit_count_1d",
    "social_media_visit_count_1d",
    "security_visit_count_1d",
    "unknown_url_ratio_1d",
    "distinct_domains_count_1d",
]


def build_user_profile(
    daily_features: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert M1 daily behavioral features into
    one behavioral profile per user.

    The current profile uses the mean daily value
    for each selected behavioral feature.
    """

    required_columns = ["user_id"] + PROFILE_FEATURES

    missing_columns = [
        column
        for column in required_columns
        if column not in daily_features.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing_columns)
        )

    if daily_features.empty:
        raise ValueError(
            "Daily feature DataFrame is empty."
        )

    profile = (
        daily_features[required_columns]
        .groupby("user_id", as_index=False)
        .mean(numeric_only=True)
    )

    feature_columns = [
        column
        for column in profile.columns
        if column != "user_id"
    ]

    if profile[feature_columns].isnull().any().any():
        raise ValueError(
            "User profile contains null values."
        )

    return profile