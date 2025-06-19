# Roboat Mission Control Backend

This is the backend service component of the Roboat Mission Control system. It provides a FastAPI-based HTTP API and WebSocket interface for real-time telemetry, mission management, and system configuration.

## Module Structure

```
roboat_mission_control/
├── api/
│   ├── __init__.py
│   ├── telemetry.py    # Telemetry and sensor data endpoints
│   └── missions.py     # Mission management endpoints
├── __init__.py
└── main.py            # FastAPI application entry point
```

## Development Setup

### Requirements
- Python 3.9 or later
- pip/virtualenv

### Installation

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install the package in editable mode:
```bash
pip install -e .
```

### Running the Service

The service can be run using uvicorn. For development with auto-reload:

```bash
uvicorn mission_control_backend.main:app --reload --host 0.0.0.0 --port 8000
```

For production:

```bash
uvicorn mission_control_backend.main:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- HTTP API: http://localhost:8000
- Interactive API documentation: http://localhost:8000/docs
- OpenAPI specification: http://localhost:8000/openapi.json

## API Overview

The service provides several groups of endpoints:

- `/`: Health check endpoint
- `/api/v1/telemetry/*`: Real-time vehicle telemetry and sensor data
- `/api/v1/missions/*`: Mission status and waypoint information

Detailed API documentation is available through the `/docs` endpoint when the service is running.