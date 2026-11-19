import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ml.features.behavioral_features import extract_behavioral_features

events = pd.DataFrame(
    [
        {
            "event_id": "ARG-HTTP-001",
            "user_id": "EMP001",
            "timestamp": "2026-08-24T09:00:00",
            "resource": "https://example.com/a",
            "device_id": "DEV001",
        },
        {
            "event_id": "ARG-HTTP-002",
            "user_id": "EMP001",
            "timestamp": "2026-08-24T10:00:00",
            "resource": "https://example.com/b",
            "device_id": "DEV001",
        },
        {
            "event_id": "ARG-HTTP-003",
            "user_id": "EMP001",
            "timestamp": "2026-08-30T22:00:00",
            "resource": "https://example.com/a",
            "device_id": "DEV002",
        },
        {
            "event_id": "ARG-HTTP-004",
            "user_id": "EMP002",
            "timestamp": "2026-08-25T11:00:00",
            "resource": "https://example.com/c",
            "device_id": "DEV003",
        },
    ]
)


features = extract_behavioral_features(events)

print("\nBehavioral features:")
print(features.to_string(index=False))