from fastapi import FastAPI
from app.api.events import router as events_router
from app.api.auth import router as auth_router

app = FastAPI(
    title="ARGUS Backend",
    description="Context-Aware Insider Threat Detection System",
    version="1.0.0"
)

app.include_router(events_router)
app.include_router(auth_router)

@app.get("/")
def root():
    return {
        "message": "ARGUS Backend is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }