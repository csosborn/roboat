from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/api/v1/missions", tags=["missions"])

class MissionStatus(BaseModel):
    id: str
    name: str
    status: str
    start_time: Optional[datetime]
    estimated_completion: Optional[datetime]
    progress_percent: float

@router.get("/current", response_model=MissionStatus)
async def get_current_mission():
    """Get current mission status."""
    return {
        "id": "mission-123",
        "name": "Bay Survey Pattern Alpha",
        "status": "in_progress",
        "start_time": datetime.utcnow(),
        "estimated_completion": datetime(2025, 6, 19, 15, 30),
        "progress_percent": 45.0
    }

class Waypoint(BaseModel):
    latitude: float
    longitude: float
    radius_meters: float
    stay_time_seconds: Optional[int]

@router.get("/current/waypoints", response_model=List[Waypoint])
async def get_current_mission_waypoints():
    """Get waypoints for the current mission."""
    return [
        {
            "latitude": 37.7749,
            "longitude": -122.4194,
            "radius_meters": 10.0,
            "stay_time_seconds": None
        },
        {
            "latitude": 37.7750,
            "longitude": -122.4195,
            "radius_meters": 10.0,
            "stay_time_seconds": 300
        }
    ]