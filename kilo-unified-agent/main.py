#!/usr/bin/env python3
"""
Kilo Unified Agent  --  Operations & Control Plane  v1.0
=========================================================
Single FastAPI entry-point that merges:

  * All k3s microservice management   (from Kilo_Ai_microservice)
  * Guardian-unified capabilities     (reasoning / plugins / personas)
  * Proactive monitoring + notifications
  * Gemini CLI deep-reasoning fallback (when quota available)

Replaces the standalone:
  ~/kilo_agent_api.py      (v4.0 agent API)
  ~/gemini_bridge.py       (Ollama-compat Gemini shim)

Port: 9200  (same as previous kilo_agent_api.py)

Endpoint map
------------
  GET  /                          -- service identity & registered service count
  GET  /health                    -- liveness probe
  GET  /services                  -- full registry dump (layer, caps, health)
  GET  /services/{name}/health    -- single-service health probe
  GET  /services/healthcheck/all  -- parallel health check all k3s services
  POST /agent/command             -- route & execute a natural-language command
  POST /agent/notify              -- push a notification into the queue
  GET  /agent/messages            -- pull recent notifications
  GET  /k3s/pods                  -- parsed pod list
  GET  /k3s/pods/{pod}/logs       -- tail pod logs
  POST /k3s/pods/{pod}/exec       -- exec command inside a pod
  POST /k3s/pods/{pod}/restart    -- delete pod (controller recreates)
  GET  /k3s/services              -- kubectl get svc -o wide
  GET  /k3s/events                -- recent cluster events
  POST /k3s/scale                 -- scale a Deployment
  GET  /k3s/resources             -- kubectl top pods
  POST /monitoring/run            -- trigger one proactive-check cycle
  GET  /monitoring/alerts         -- current open alerts
  GET  /data/monitoring           -- proactive monitor status / stats
  POST /v1/chat/completions       -- OpenAI-compat Gemini bridge
  POST /api/generate              -- Ollama-compat Gemini bridge
"""

import logging
import os
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from service_registry  import ServiceRegistry, resolve_cluster_ips
from k3s_controller    import (
    get_pods, get_pod_logs, exec_in_pod,
    restart_pod, get_services, get_events,
    scale_deployment, get_resource_usage,
)
from command_router    import route_command, call_k3s_service, call_gemini, call_guardian_service, precompute_service_embeddings
from proactive_monitor import ProactiveMonitor

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("KiloUnifiedAgent")

# ---------------------------------------------------------------------------
app = FastAPI(title="Kilo Unified Agent", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------
registry = ServiceRegistry()


class _MQ:
    """Simple in-memory notification queue with TTL filtering."""

    def __init__(self, max_size: int = 200):
        self._q: deque = deque(maxlen=max_size)

    def push(self, msg: Dict):
        msg.setdefault("timestamp", datetime.now().isoformat())
        self._q.append(msg)

    def recent(self, count: int = 20, since_minutes: int = 60) -> List[Dict]:
        cutoff = datetime.now() - timedelta(minutes=since_minutes)
        out = []
        for m in self._q:
            try:
                if datetime.fromisoformat(m["timestamp"]) >= cutoff:
                    out.append(m)
            except (KeyError, ValueError):
                out.append(m)
        return out[-count:]


mq = _MQ()


async def _on_alert(alert: Dict):
    """Callback: proactive monitor pushes here."""
    mq.push(alert)


monitor = ProactiveMonitor(registry=registry, notify=_on_alert)



# ---------------------------------------------------------------------------
# Startup: resolve ClusterIPs so host-mode service calls work
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    await resolve_cluster_ips(registry)
    precompute_service_embeddings(registry)
    logger.info("Service URLs resolved. Registry ready.")

# ---------------------------------------------------------------------------
# Pydantic request bodies
# ---------------------------------------------------------------------------

class CommandReq(BaseModel):
    command: str
    params: Dict[str, Any] = {}


class NotifyReq(BaseModel):
    type:     str            = "notification"
    content:  str
    priority: str            = "normal"
    metadata: Dict[str, Any] = {}


class ExecReq(BaseModel):
    command: List[str]


class ScaleReq(BaseModel):
    deployment: str
    replicas:   int


# ---------------------------------------------------------------------------
# Root / health
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "service":             "Kilo Unified Agent",
        "version":             "1.0.0",
        "status":              "running",
        "registered_services": len(registry.services),
        "layers":              ["k3s", "guardian", "host"],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "ts": datetime.now().isoformat()}


# ---------------------------------------------------------------------------
# Service registry
# ---------------------------------------------------------------------------
@app.get("/services")
async def list_services():
    return registry.get_status()


@app.get("/services/{name}/health")
async def svc_health(name: str):
    ok = await registry.health_check(name)
    return {"service": name, "healthy": ok}


@app.get("/services/healthcheck/all")
async def svc_health_all():
    res = await registry.health_check_all()
    return {
        "results":      res,
        "healthy_count": sum(res.values()),
        "total":        len(res),
    }


# ---------------------------------------------------------------------------
# K3s cluster operations
# ---------------------------------------------------------------------------
@app.get("/k3s/pods")
async def kube_pods():
    return await get_pods()


@app.get("/k3s/pods/{pod}/logs")
async def kube_logs(pod: str, tail: int = 50):
    return await get_pod_logs(pod, tail=tail)


@app.post("/k3s/pods/{pod}/exec")
async def kube_exec(pod: str, req: ExecReq):
    return await exec_in_pod(pod, req.command)


@app.post("/k3s/pods/{pod}/restart")
async def kube_restart(pod: str):
    return await restart_pod(pod)


@app.get("/k3s/services")
async def kube_services():
    return await get_services()


@app.get("/k3s/events")
async def kube_events():
    return await get_events()


@app.post("/k3s/scale")
async def kube_scale(req: ScaleReq):
    return await scale_deployment(req.deployment, req.replicas)


@app.get("/k3s/resources")
async def kube_resources():
    return await get_resource_usage()


# ---------------------------------------------------------------------------
# Agent command routing
# ---------------------------------------------------------------------------
@app.post("/agent/command")
async def agent_command(req: CommandReq):
    """
    Route flow:
      keyword match -> direct k3s service call  (fast path)
                    -> guardian target          -> Gemini with context
                    -> no match / call failed   -> Gemini fallback
    """
    target, conf = route_command(req.command, registry)
    logger.info("route: '%s' -> %s (conf=%.2f)", req.command[:60], target, conf)

    # --- local cluster ops ---
    if target == "k3s_ops":
        return await _k3s_command(req.command)

    # --- system health summary ---
    if target == "system_health":
        res = await registry.health_check_all()
        unhealthy = [n for n, ok in res.items() if not ok]
        return {
            "success":   True,
            "message":   f"{sum(res.values())}/{len(res)} services healthy",
            "unhealthy": unhealthy,
        }

    # --- help ---
    if target == "help":
        return {"success": True, "message": _HELP}

    # --- unified k3s + guardian routing ---
    is_guardian = target in ("guardian", "reasoning-engine", "plugin-manager", "persona-manager", 
                            "drone-control", "meshtastic", "security-monitor")
    
    if is_guardian:
        result = await call_guardian_service(req.command, registry)
    else:
        result = await call_k3s_service(target, req.command, registry)

    if result.get("success"):
        return result

    # --- catch-all: Gemini deep-reasoning ---
    return await call_gemini(req.command)


async def _k3s_command(cmd: str) -> Dict[str, Any]:
    """Parse simple cluster-operation commands from natural language."""
    lower = cmd.lower()

    if "log" in lower:
        for word in lower.split():
            if word.startswith("kilo-"):
                return await get_pod_logs(word)
        return {"success": False, "message": "Specify pod name: 'logs kilo-<name>'"}

    if "restart" in lower:
        for word in lower.split():
            if word.startswith("kilo-"):
                return await restart_pod(word)
        return {"success": False, "message": "Specify pod name: 'restart kilo-<name>'"}

    if "event" in lower:
        return await get_events()

    if "resource" in lower or "top" in lower:
        return await get_resource_usage()

    # default: list pods
    return await get_pods()


# ---------------------------------------------------------------------------
# Notifications / message queue
# ---------------------------------------------------------------------------
@app.post("/agent/notify")
async def notify(req: NotifyReq):
    mq.push({
        "type":     req.type,
        "content":  req.content,
        "priority": req.priority,
        "metadata": req.metadata,
    })
    return {"status": "ok"}


@app.get("/agent/messages")
async def messages(since_minutes: int = 60, count: int = 20):
    return {"messages": mq.recent(count=count, since_minutes=since_minutes)}

# Alias /messages to /agent/messages for frontend compatibility
@app.get("/messages")
async def messages_alias(since_minutes: int = 60, count: int = 20):
    return await messages(since_minutes=since_minutes, count=count)


# ---------------------------------------------------------------------------
# Proactive monitoring
# ---------------------------------------------------------------------------
@app.post("/monitoring/run")
async def mon_run():
    alerts = await monitor.run_checks()
    return {"alerts": alerts, "count": len(alerts)}


@app.get("/monitoring/alerts")
async def mon_alerts():
    return {"alerts": [m for m in mq.recent(since_minutes=120) if m.get("severity")]}


@app.get("/data/monitoring")
async def mon_data():
    # Return monitor status and summary stats
    res = await monitor.get_status()
    return res


# ---------------------------------------------------------------------------
# Gemini bridge  (drop-in replacement for ~/gemini_bridge.py)
#   POST /v1/chat/completions   -- OpenAI format
#   POST /api/generate          -- Ollama format
# ---------------------------------------------------------------------------
async def _gemini_bridge(request: Request):
    body = await request.json()
    if "messages" in body:
        prompt = (body["messages"] or [{}])[-1].get("content", "")
    else:
        prompt = body.get("prompt", "Hello")

    result = await call_gemini(prompt)
    text   = result.get("message", "")
    return {
        "choices":  [{"message": {"role": "assistant", "content": text}}],
        "response": text,       # Ollama compat
    }


app.add_api_route("/v1/chat/completions", _gemini_bridge, methods=["POST"])
app.add_api_route("/api/generate",        _gemini_bridge, methods=["POST"])


# ---------------------------------------------------------------------------
# File system access API — lets Kilo's pod read/list/scan/delete files
# ---------------------------------------------------------------------------
import os as _os, stat as _stat, hashlib as _hashlib

_SUSPICIOUS_EXT = {".exe",".msi",".bat",".cmd",".vbs",".ps1",".sh",".bash",
                   ".jar",".apk",".appimage",".deb",".rpm"}
_BAD_PATTERNS = [b"eval(base64",b"exec(base64",b"powershell -enc",b"/dev/tcp/",
                 b"nc -e ",b"bash -i ",b"rm -rf /",b"xmrig",b"stratum+tcp",
                 b"chmod 777",b"wget http",b"curl http"]

@app.get("/files/list")
async def files_list(path: str, max_entries: int = 100):
    """List directory contents."""
    if not _os.path.exists(path):
        raise HTTPException(404, f"Path not found: {path}")
    if not _os.path.isdir(path):
        raise HTTPException(400, f"Not a directory: {path}")
    entries = []
    for name in sorted(_os.listdir(path))[:max_entries]:
        full = _os.path.join(path, name)
        try:
            s = _os.stat(full)
            entries.append({"name": name, "type": "dir" if _os.path.isdir(full) else "file",
                            "size": s.st_size, "modified": s.st_mtime})
        except Exception:
            entries.append({"name": name, "type": "unknown"})
    return {"path": path, "count": len(entries), "entries": entries}


@app.get("/files/read")
async def files_read(path: str, max_lines: int = 100):
    """Read a file."""
    if not _os.path.exists(path):
        raise HTTPException(404, f"File not found: {path}")
    if _os.path.isdir(path):
        raise HTTPException(400, "Is a directory, use /files/list")
    size = _os.path.getsize(path)
    with open(path, "r", errors="replace") as f:
        lines = f.readlines()
    truncated = len(lines) > max_lines
    return {"path": path, "size": size, "total_lines": len(lines),
            "truncated": truncated, "content": "".join(lines[:max_lines])}


@app.get("/files/scan")
async def files_scan(path: str, recursive: bool = False):
    """Security scan a directory for suspicious files."""
    if not _os.path.exists(path):
        raise HTTPException(404, f"Path not found: {path}")
    flagged = []
    scanned = 0
    walk = _os.walk(path) if recursive else [(path, [], _os.listdir(path))]
    for root, dirs, files in walk:
        for fname in files:
            if scanned >= 300:
                break
            scanned += 1
            full = _os.path.join(root, fname)
            _, ext = _os.path.splitext(fname.lower())
            reasons, risk = [], "clean"
            if ext in _SUSPICIOUS_EXT:
                reasons.append(f"suspicious extension ({ext})")
                risk = "medium"
            try:
                with open(full, "rb") as f:
                    head = f.read(8192)
                if head[:4] in (b"\x7fELF", b"MZ\x90\x00"):
                    reasons.append("binary executable")
                    risk = "medium" if risk == "clean" else risk
                head_lower = head.lower()
                for pat in _BAD_PATTERNS:
                    if pat in head_lower:
                        risk = "HIGH"
                        reasons.append(f"bad pattern: {pat[:25].decode('utf-8','replace')}")
            except Exception as e:
                reasons.append(f"read error: {e}")
            if risk != "clean":
                flagged.append({"path": full, "risk": risk, "reasons": reasons})
        if scanned >= 300:
            break
    return {"path": path, "scanned": scanned, "flagged": flagged,
            "summary": f"Scanned {scanned} files, {len(flagged)} flagged"}


@app.delete("/files/delete")
async def files_delete(path: str):
    """Delete a file."""
    if not path or path in ("/", "/home", "/home/brain_ai"):
        raise HTTPException(400, "Refusing to delete that path")
    if not _os.path.exists(path):
        raise HTTPException(404, f"Not found: {path}")
    _os.remove(path)
    return {"deleted": path, "status": "ok"}


# ---------------------------------------------------------------------------
# Screen capture — screenshot → Gemini Vision → extract data → save to pods
# ---------------------------------------------------------------------------
import base64 as _base64

_GATEWAY_URL   = os.getenv("KILO_GATEWAY_URL", "http://192.168.68.57:30801")
_FINANCIAL_URL = os.getenv("KILO_FINANCIAL_URL", "http://192.168.68.57:30801/api/financial/transactions")

_FINANCIAL_PROMPT = (
    "This is a screenshot of a bank register, transaction list, or financial page. "
    "Extract ALL visible transactions. For each return: date (YYYY-MM-DD), "
    "description/merchant, amount (negative for debits, positive for credits), category. "
    'Respond ONLY as JSON: {"transactions": [{"date": "YYYY-MM-DD", "description": "...", '
    '"amount": -12.34, "category": "..."}]}. '
    'If no transactions are visible, return {"transactions": []}.'
)

_GENERAL_PROMPT = (
    "Describe what is visible on this screen. If there are numbers, tables, lists, "
    "transactions, or any structured data, extract and list them clearly."
)


class CaptureRequest(BaseModel):
    mode: str = "financial"   # "financial" | "general"
    save_transactions: bool = True


@app.post("/screen/capture")
async def screen_capture(req: CaptureRequest):
    """Take a screenshot, send to Gemini Vision, optionally save financial transactions."""
    import tempfile as _tmp

    # Capture screenshot
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"/tmp/kilo_capture_{ts}.png"
    try:
        result = _subprocess.run(["scrot", "-o", path], capture_output=True, timeout=5)
        if result.returncode != 0:
            result = _subprocess.run(["gnome-screenshot", "-f", path], capture_output=True, timeout=5)
        if result.returncode != 0 or not _os.path.exists(path):
            raise RuntimeError("Screenshot failed")
    except FileNotFoundError:
        raise HTTPException(500, "No screenshot tool — install scrot")
    except Exception as e:
        raise HTTPException(500, f"Screenshot error: {e}")

    try:
        with open(path, "rb") as f:
            img_b64 = _base64.b64encode(f.read()).decode()
    finally:
        try:
            _os.remove(path)
        except Exception:
            pass

    prompt = _FINANCIAL_PROMPT if req.mode == "financial" else _GENERAL_PROMPT

    # Send to Gemini Vision via ai-brain
    try:
        async with _httpx.AsyncClient(timeout=45.0) as client:
            vision_resp = await client.post(
                f"{_GATEWAY_URL}/api/ai_brain/vision/analyze",
                json={"image_base64": img_b64, "prompt": prompt, "source": "screen_capture"},
            )
            vision_resp.raise_for_status()
            result_text = vision_resp.json().get("result", "")
    except Exception as e:
        raise HTTPException(502, f"Vision analyze failed: {e}")

    # Parse and save transactions if financial mode
    transactions_saved = 0
    errors = []
    parsed_transactions = []

    if req.mode == "financial" and req.save_transactions:
        import json as _json, re as _re
        data = None
        fence = _re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, _re.DOTALL)
        if fence:
            try:
                data = _json.loads(fence.group(1))
            except Exception:
                pass
        if not data:
            brace = _re.search(r'\{.*\}', result_text, _re.DOTALL)
            if brace:
                try:
                    data = _json.loads(brace.group())
                except Exception:
                    pass

        if data:
            parsed_transactions = data.get("transactions", [])

            # --- Deduplication: fetch existing transactions and skip matches ---
            existing_keys: set = set()
            try:
                async with _httpx.AsyncClient(timeout=10.0) as client:
                    existing_resp = await client.get(
                        f"{_GATEWAY_URL}/api/financial/transactions",
                        params={"limit": 500},
                    )
                    if existing_resp.status_code == 200:
                        existing = existing_resp.json()
                        if isinstance(existing, list):
                            rows = existing
                        else:
                            rows = existing.get("transactions", [])
                        for row in rows:
                            key = (
                                str(row.get("date", ""))[:10],
                                str(row.get("description", "")).strip().lower()[:40],
                                round(float(row.get("amount", 0)), 2),
                            )
                            existing_keys.add(key)
            except Exception as e:
                errors.append(f"dedup fetch error: {e}")

            duplicates_skipped = 0
            async with _httpx.AsyncClient(timeout=10.0) as client:
                for tx in parsed_transactions:
                    tx_key = (
                        str(tx.get("date", ""))[:10],
                        str(tx.get("description", "")).strip().lower()[:40],
                        round(float(tx.get("amount", 0)), 2),
                    )
                    if tx_key in existing_keys:
                        duplicates_skipped += 1
                        continue
                    try:
                        r = await client.post(_FINANCIAL_URL, json={
                            "date":        tx.get("date", ""),
                            "description": tx.get("description", "unknown"),
                            "amount":      float(tx.get("amount", 0)),
                            "category":    tx.get("category", "bank_screen"),
                            "source":      "screen_ocr",
                        })
                        if r.status_code in (200, 201):
                            transactions_saved += 1
                            existing_keys.add(tx_key)  # prevent re-adding in same batch
                        else:
                            errors.append(f"{tx.get('description','?')}: {r.status_code}")
                    except Exception as e:
                        errors.append(str(e))

            if duplicates_skipped:
                errors.insert(0, f"skipped {duplicates_skipped} duplicates already in pod")

    return {
        "mode":                  req.mode,
        "vision_result":         result_text[:500],
        "transactions_found":    len(parsed_transactions),
        "transactions_saved":    transactions_saved,
        "duplicates_skipped":    duplicates_skipped if req.mode == "financial" else 0,
        "errors":                errors[:5],
        "raw_result":            result_text,
    }


# ---------------------------------------------------------------------------
# Voice / TTS — Kilo speaks through desktop speakers
# ---------------------------------------------------------------------------
import subprocess as _subprocess
import tempfile as _tempfile
import httpx as _httpx

_TTS_URL = os.getenv("KILO_TTS_URL", "http://192.168.68.57:30801/api/voice/tts")
_PULSE_ENV = {
    "PULSE_RUNTIME_PATH": f"/run/user/{os.getuid()}",
    "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
    "HOME": os.path.expanduser("~"),
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    "DISPLAY": os.environ.get("DISPLAY", ":0"),
}


class SpeakRequest(BaseModel):
    text: str
    voice: str = "kilo"
    priority: str = "normal"  # "high" skips queue, plays immediately


@app.post("/speak")
async def speak(req: SpeakRequest):
    """Fetch TTS audio from kilo-voice and play through desktop speakers."""
    text = req.text.strip()[:1000]
    if not text:
        raise HTTPException(400, "text is required")

    # Fetch MP3 from kilo-voice via gateway
    try:
        async with _httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                _TTS_URL,
                params={"text": text, "voice": req.voice},
            )
            resp.raise_for_status()
            audio_bytes = resp.content
    except Exception as e:
        raise HTTPException(502, f"TTS fetch failed: {e}")

    # Write to temp file and play via ffplay (non-blocking, quiet)
    try:
        with _tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        _subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
            env=_PULSE_ENV,
            stdout=_subprocess.DEVNULL,
            stderr=_subprocess.DEVNULL,
        )
        return {"status": "playing", "chars": len(text), "voice": req.voice}
    except Exception as e:
        raise HTTPException(500, f"Playback failed: {e}")


@app.get("/speak/test")
async def speak_test():
    """Quick smoke test — plays a short phrase through speakers."""
    from fastapi.responses import JSONResponse
    result = await speak(SpeakRequest(text="Kilo voice test — speakers are working."))
    return result


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------
_HELP = """\
=== Kilo Unified Agent  v1.0 ===
Commands are routed automatically by keyword.  Examples:

  reminders            list / check reminders
  habits               habit tracking & streaks
  meds                 medication status & adherence
  budget / spending    financial overview & alerts
  camera               camera & monitoring status
  voice                voice / speech commands
  library              knowledge-base search
  pods / k3s           cluster management (list, logs, restart, scale)
  health / status      full system health check
  drone                drone control  (guardian)
  mesh                 Meshtastic mesh tracking
  persona / mode       switch persona (home / pro / business)
  security             security & intrusion alerts

Anything not matched above is forwarded to Gemini for deep reasoning
across host, cluster, and pod-interior layers.
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("KILO_AGENT_PORT", "9200"))
    logger.info("Starting Kilo Unified Agent on port %d", port)
    logger.info("Registered services: %s", list(registry.services.keys()))
    uvicorn.run(app, host="0.0.0.0", port=port)