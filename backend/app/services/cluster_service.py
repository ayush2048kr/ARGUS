import csv
import math
from datetime import datetime, timezone
from pathlib import Path

from pymongo import UpdateOne

from app.database.mongodb import (
    cluster_summaries_collection,
    cluster_assignments_collection,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = PROJECT_ROOT / "ml" / "evaluation" / "output"
MODEL_KEY = "kmeans_k3"


def read_csv(filename):
    path = OUTPUT_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Required cluster output not found: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite number in cluster output")
    return result


def integer(value):
    return int(float(value))


def import_cluster_outputs():
    sizes = read_csv("kmeans_k3_cluster_sizes.csv")
    profiles = read_csv("kmeans_k3_cluster_profiles.csv")
    assignments = read_csv("kmeans_k3_user_clusters.csv")
    top_features = read_csv("kmeans_k3_top_features.csv")
    metrics = read_csv("kmeans_evaluation_metrics.csv")

    required = [
        (sizes, {"cluster_id", "user_count", "percentage"}, "sizes"),
        (profiles, {"cluster_id"}, "profiles"),
        (assignments, {"user_id", "cluster_id"}, "assignments"),
        (top_features, {
            "cluster_id", "feature", "standardized_centroid",
            "absolute_deviation", "direction"
        }, "top features"),
        (metrics, {
            "k", "silhouette_score", "davies_bouldin_index", "inertia"
        }, "metrics"),
    ]

    for rows, columns, label in required:
        if not rows or not columns.issubset(rows[0]):
            raise ValueError(f"Invalid or empty cluster {label} CSV")

    profile_map = {
        integer(row["cluster_id"]): {
            key: number(value)
            for key, value in row.items()
            if key != "cluster_id" and value not in ("", None)
        }
        for row in profiles
    }

    feature_map = {}
    for row in top_features:
        cluster_id = integer(row["cluster_id"])
        feature_map.setdefault(cluster_id, []).append({
            "feature": row["feature"],
            "standardized_centroid": number(row["standardized_centroid"]),
            "absolute_deviation": number(row["absolute_deviation"]),
            "direction": row["direction"],
        })

    clusters = []
    for row in sizes:
        cluster_id = integer(row["cluster_id"])
        clusters.append({
            "cluster_id": cluster_id,
            "user_count": integer(row["user_count"]),
            "percentage": number(row["percentage"]),
            "profile": profile_map.get(cluster_id, {}),
            "top_features": feature_map.get(cluster_id, []),
        })

    user_ids = [row["user_id"].strip() for row in assignments]
    if any(not user_id for user_id in user_ids):
        raise ValueError("Empty user ID in cluster assignments")
    if len(user_ids) != len(set(user_ids)):
        raise ValueError("Duplicate user IDs in cluster assignments")

    valid_cluster_ids = {item["cluster_id"] for item in clusters}
    operations = []
    now = datetime.now(timezone.utc)

    for row in assignments:
        user_id = row["user_id"].strip()
        cluster_id = integer(row["cluster_id"])

        if cluster_id not in valid_cluster_ids:
            raise ValueError(f"Unknown cluster ID for {user_id}: {cluster_id}")

        operations.append(UpdateOne(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "cluster_id": cluster_id,
                "model_key": MODEL_KEY,
                "updated_at": now,
            }},
            upsert=True,
        ))

    if operations:
        cluster_assignments_collection.bulk_write(operations, ordered=True)

    summary = {
        "model_key": MODEL_KEY,
        "algorithm": "K-Means",
        "cluster_count": len(clusters),
        "user_count": len(assignments),
        "clusters": clusters,
        "evaluation_metrics": [
            {
                "k": integer(row["k"]),
                "silhouette_score": number(row["silhouette_score"]),
                "davies_bouldin_index": number(row["davies_bouldin_index"]),
                "inertia": number(row["inertia"]),
            }
            for row in metrics
        ],
        "updated_at": now,
    }

    cluster_summaries_collection.update_one(
        {"model_key": MODEL_KEY},
        {"$set": summary},
        upsert=True,
    )

    return {
        "model_key": MODEL_KEY,
        "clusters_imported": len(clusters),
        "users_imported": len(assignments),
        "evaluation_rows_imported": len(metrics),
    }


def get_cluster_summary():
    return cluster_summaries_collection.find_one(
        {"model_key": MODEL_KEY},
        {"_id": 0},
    )


def get_cluster_users(cluster_id, limit=100):
    return list(
        cluster_assignments_collection.find(
            {"model_key": MODEL_KEY, "cluster_id": cluster_id},
            {"_id": 0, "user_id": 1, "cluster_id": 1},
        )
        .sort("user_id", 1)
        .limit(limit)
    )


def get_user_cluster(user_id):
    return cluster_assignments_collection.find_one(
        {"model_key": MODEL_KEY, "user_id": user_id},
        {"_id": 0},
    )
