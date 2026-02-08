from fastapi import FastAPI, Body
from kilo_v2.security_monitor import SecurityMonitor
import uvicorn

app = FastAPI(title="Kilo Security Microservice")
monitor = SecurityMonitor()

@app.on_event("startup")
async def startup():
    monitor.start_monitoring()

@app.post("/api/chat")
async def chat(query: str = Body(..., embed=True)):
    return {"answer": f"Security Monitor active. Query processed: {query}"}

@app.get("/api/network/stats")
async def network_stats():
    return monitor.get_status()

@app.get("/api/network/devices")
async def network_devices():
    return {
        "connections": monitor.network_monitor.get_active_connections(),
        "suspicious_ips": list(monitor.network_monitor.suspicious_ips)
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)