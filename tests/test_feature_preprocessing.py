import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ml.features.feature_preprocessing import prepare_feature_matrix


features = pd.DataFrame(
    [
        {
            "user_id": "EMP001",
            "activity_frequency": 100,
            "resource_access_frequency": 80,
            "unique_resource_count": 20,
            "unique_device_count": 2,
            "weekday_activity": 90,
            "weekend_activity": 10,
            "hour_9": 30,
            "hour_10": 40,
            "hour_11": 30,
        },
        {
            "user_id": "EMP002",
            "activity_frequency": 20,
            "resource_access_frequency": 15,
            "unique_resource_count": 5,
            "unique_device_count": 1,
            "weekday_activity": 20,
            "weekend_activity": 0,
            "hour_9": 10,
            "hour_10": 5,
            "hour_11": 5,
        },
        {
            "user_id": "EMP003",
            "activity_frequency": 60,
            "resource_access_frequency": 50,
            "unique_resource_count": 12,
            "unique_device_count": 3,
            "weekday_activity": 45,
            "weekend_activity": 15,
            "hour_9": 20,
            "hour_10": 20,
            "hour_11": 20,
        },
    ]
)


user_ids, scaled_features = prepare_feature_matrix(
    features
)

print("\nUser IDs:")
print(user_ids.to_string(index=False))

print("\nScaled features:")
print(scaled_features.to_string(index=False))

print("\nFeature means:")
print(scaled_features.mean().round(6).to_string())

print("\nFeature standard deviations:")
print(
    scaled_features.std(ddof=0)
    .round(6)
    .to_string()
)