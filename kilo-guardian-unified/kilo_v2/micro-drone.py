import os
import sys
import asyncio
from fastapi import FastAPI, Body
import uvicorn

# Fix path for plugin imports
base_dir = os.path.dirname(__file__)
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from kilo_v2.plugins.drone_control import DroneControl

app = FastAPI(title="Kilo Drone Microservice")
plugin = DroneControl()

@app.on_event("startup")
async def startup():
    # Start background tasks for telemetry
    plugin.start_background_task()

@app.post("/api/chat")
async def chat(query: str = Body(..., embed=True)):
    result = plugin.execute(query)
    return {"answer": result}

@app.get("/api/drone/status")
async def drone_status():
    # Attempt to get latest telemetry if possible
    status = plugin.health()
    # Add latest telemetry to the status response
    status["telemetry"] = getattr(plugin, "_latest_telemetry", {})
    status["connected"] = getattr(plugin, "_connected", False)
    status["armed"] = getattr(plugin, "_armed", False)
    return status

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
