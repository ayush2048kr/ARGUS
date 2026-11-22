
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from app.api.events import router as events_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.alerts import router as alerts_router
from app.api.risks import router as risks_router
from app.api.dashboard import router as dashboard_router
from app.api.daily_risks import router as daily_risks_router
from app.api.clusters import router as clusters_router

from app.database.mongodb import (
    initialize_database,
    check_database_connection,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="ARGUS Backend",
    description="Context-Aware Insider Threat Detection System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(alerts_router)
app.include_router(risks_router)
app.include_router(daily_risks_router)
app.include_router(clusters_router)
app.include_router(dashboard_router)


@app.get("/")
def root():
    return {"message": "ARGUS Backend is running"}


@app.get("/health")
def health_check():
    try:
        check_database_connection()
        return {"status": "healthy"}
    except PyMongoError:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "unavailable",
            },
        )
