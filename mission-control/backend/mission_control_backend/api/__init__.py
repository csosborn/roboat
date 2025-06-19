"""
API endpoints for the Roboat Mission Control system.
"""

from .telemetry import router as telemetry_router
from .missions import router as missions_router

__all__ = ["telemetry_router", "missions_router"]