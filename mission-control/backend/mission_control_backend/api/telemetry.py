from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])

class TelemetryData(BaseModel):
    timestamp: datetime
    latitude: float
    longitude: float
    heading: float
    battery_percentage: float
    solar_power_watts: float
    speed_knots: float

@router.get("/current", response_model=TelemetryData)
async def get_current_telemetry():
    """Get current telemetry data."""
    return {
        "timestamp": datetime.utcnow(),
        "latitude": 37.7749,
        "longitude": -122.4194,
        "heading": 90.0,
        "battery_percentage": 85.0,
        "solar_power_watts": 250.0,
        "speed_knots": 2.5
    }

class SystemHealth(BaseModel):
    status: str
    cpu_temp: float
    memory_usage: float
    disk_usage: float

@router.get("/health", response_model=SystemHealth)
async def get_system_health():
    """Get system health metrics."""
    return {
        "status": "nominal",
        "cpu_temp": 45.2,
        "memory_usage": 32.5,
        "disk_usage": 28.7
    }

class EnvironmentalData(BaseModel):
    wind_speed_knots: float
    wind_direction: float
    water_temp_celsius: float
    air_temp_celsius: float
    wave_height_meters: float

@router.get("/environmental", response_model=EnvironmentalData)
async def get_environmental_data():
    """Get environmental sensor data."""
    return {
        "wind_speed_knots": 8.5,
        "wind_direction": 180.0,
        "water_temp_celsius": 18.5,
        "air_temp_celsius": 22.0,
        "wave_height_meters": 0.5
    }