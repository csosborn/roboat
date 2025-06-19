from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mission_control_backend.api import telemetry_router, missions_router

app = FastAPI(
    title="Roboat Mission Control",
    description="API backend for the Roboat Mission Control system",
    version="0.1.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include our API routers
app.include_router(telemetry_router)
app.include_router(missions_router)

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "roboat-mission-control"}