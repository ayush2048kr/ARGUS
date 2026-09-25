import pandas as pd
from sklearn.preprocessing import StandardScaler


ID_COLUMN = "user_id"


def prepare_feature_matrix(
    features: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Prepare user-level behavioral features for ML.

    Parameters
    ----------
    features : pd.DataFrame
        Output produced by extract_behavioral_features().

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        user_ids:
            DataFrame containing user IDs.

        scaled_features:
            DataFrame containing standardized numerical
            behavioral features.

    Notes
    -----
    User IDs are kept separately and are never used as
    numerical clustering features.
    """

    if features.empty:
        raise ValueError("Feature DataFrame is empty.")

    if ID_COLUMN not in features.columns:
        raise ValueError(
            f"Required identifier column '{ID_COLUMN}' is missing."
        )

    # -----------------------------------------------------
    # 1. Separate user identifiers
    # -----------------------------------------------------

    user_ids = features[[ID_COLUMN]].copy()

    # -----------------------------------------------------
    # 2. Select numerical behavioral features
    # -----------------------------------------------------

    feature_data = features.drop(
        columns=[ID_COLUMN]
    ).copy()

    if feature_data.empty:
        raise ValueError(
            "No behavioral features available for ML."
        )

    # -----------------------------------------------------
    # 3. Validate numerical data
    # -----------------------------------------------------

    non_numeric_columns = feature_data.select_dtypes(
        exclude="number"
    ).columns.tolist()

    if non_numeric_columns:
        raise ValueError(
            "Non-numeric feature columns found: "
            + ", ".join(non_numeric_columns)
        )

    if feature_data.isnull().any().any():
        raise ValueError(
            "Behavioral feature matrix contains null values."
        )

    # -----------------------------------------------------
    # 4. Standardize features
    # -----------------------------------------------------

    scaler = StandardScaler()

    scaled_values = scaler.fit_transform(
        feature_data
    )

    scaled_features = pd.DataFrame(
        scaled_values,
        columns=feature_data.columns,
        index=feature_data.index,
    )

    return user_ids, scaled_features