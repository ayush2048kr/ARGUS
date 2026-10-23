from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.events import router as events_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.alerts import router as alerts_router
from app.api.risks import router as risks_router
from app.api.dashboard import router as dashboard_router

app = FastAPI(
    title="ARGUS Backend",
    description="Context-Aware Insider Threat Detection System",
    version="1.0.0",
)

# Allow the local React/Vite development server to call the API.
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
app.include_router(dashboard_router)


@app.get("/")
def root():
    return {"message": "ARGUS Backend is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
