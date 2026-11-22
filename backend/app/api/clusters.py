from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.errors import PyMongoError

from app.auth.dependencies import require_role
from app.services.cluster_service import (
    get_cluster_summary,
    get_cluster_users,
    get_user_cluster,
)

router = APIRouter(prefix="/clusters", tags=["Behavior Clusters"])


@router.get("/summary")
def cluster_summary(
    current_user: dict = Depends(require_role(["admin", "analyst"])),
):
    try:
        result = get_cluster_summary()
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Cluster data has not been imported",
            )
        return result
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database unavailable")


@router.get("/users/{user_id}")
def user_cluster(
    user_id: str,
    current_user: dict = Depends(require_role(["admin", "analyst"])),
):
    try:
        result = get_user_cluster(user_id)
        if result is None:
            raise HTTPException(status_code=404, detail="User cluster not found")
        return result
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database unavailable")


@router.get("/{cluster_id}/users")
def cluster_users(
    cluster_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: dict = Depends(require_role(["admin", "analyst"])),
):
    if cluster_id < 0:
        raise HTTPException(status_code=422, detail="Invalid cluster ID")

    try:
        summary = get_cluster_summary()
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail="Cluster data has not been imported",
            )

        known_ids = {item["cluster_id"] for item in summary["clusters"]}
        if cluster_id not in known_ids:
            raise HTTPException(status_code=404, detail="Cluster not found")

        return {
            "cluster_id": cluster_id,
            "users": get_cluster_users(cluster_id, limit),
        }
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database unavailable")
