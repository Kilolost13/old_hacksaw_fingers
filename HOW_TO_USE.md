# How to Use Kilo Guardian - Simple Guide

## 🎯 What Each Component Does

### 1. **Frontend (http://192.168.68.56:30002)**
This is your **main interface** - the web app you interact with.

**What you should see:**
- A React web application
- Likely has: Navigation, Dashboard, Chat interface
- Responsive design (works on phone/tablet too)

**What you can do:**
- View dashboard/status
- Chat with the AI
- Manage tasks/reminders
- View health metrics

---

### 2. **Gateway API (http://192.168.68.56:30801)**
This is the **backend router** that connects all services.

**How to test:**
```bash
curl http://192.168.68.56:30801/health
# Should return: {"status":"ok"}
```

**What it provides:**
- Routes requests to microservices
- Handles authentication
- Manages data flow

---

### 3. **Agent API (http://localhost:9100)**
This is the **supervisory AI engine** that coordinates everything.

**How to test:**
```bash
curl http://localhost:9100/agent/status
# Should return: {"status":"ok","queue_size":0,...}
```

**Available endpoints:**
- `GET /agent/status` - Check agent status
- `GET /agent/messages` - Get notifications
- `POST /agent/notify` - Send notifications
- `POST /agent/command` - Send commands
- `GET /docs` - Interactive API documentation

---

### 4. **Microservices (in Kubernetes)**
19 services running in K3s, including:

| Service | Purpose |
|---------|---------|
| `kilo-ai-brain` | AI decision making |
| `kilo-gateway` | API router |
| `kilo-frontend` | React UI |
| `kilo-reminder` | Reminder management |
| `kilo-financial` | Budget tracking |
| `kilo-habits` | Habit tracking |
| `kilo-meds` | Medication tracking |
| `kilo-voice` | Text-to-speech |
| `kilo-cam` | Camera/vision |
| `kilo-socketio` | Real-time updates |
| ... and more |

---

## 📱 Quick Start: Using the System

### Step 1: Open Frontend
```
Open in browser: http://192.168.68.56:30002
```

### Step 2: Interact with AI
- Look for chat interface
- Type a message
- AI should respond

### Step 3: Monitor Status
- Dashboard should show system status
- Check microservice health
- View notifications

---

## 🔧 Testing Endpoints

### Test All Services at Once
```bash
bash troubleshoot.sh
```

### Test Individual Services

**Test Frontend:**
```bash
curl -I http://192.168.68.56:30002
```

**Test Gateway:**
```bash
curl http://192.168.68.56:30801/health
```

**Test Agent API:**
```bash
curl http://localhost:9100/agent/status
```

**Test AI Brain:**
```bash
kubectl logs -n kilo-guardian -f deployment/kilo-ai-brain
```

---

## ❓ Common Issues & Fixes

### Issue: Frontend doesn't load

**Fix 1:** Check service status
```bash
kubectl get pods -n kilo-guardian -l app=kilo-frontend
```

**Fix 2:** Check logs
```bash
kubectl logs -n kilo-guardian -l app=kilo-frontend -f
```

**Fix 3:** Restart service
```bash
kubectl rollout restart deployment/kilo-frontend -n kilo-guardian
```

---

### Issue: AI doesn't respond

**Fix 1:** Check Agent API
```bash
curl http://localhost:9100/agent/status
```

**Fix 2:** Check if process is running
```bash
ps aux | grep kilo_agent_api
netstat -tlnp | grep 9100
```

**Fix 3:** Restart Agent API
```bash
pkill -f kilo_agent_api
source venv/bin/activate
python3 kilo_agent_api.py > logs/agent-api.log 2>&1 &
```

---

### Issue: Can't reach services from phone/tablet

**Solution 1:** Use SSH tunnel
```bash
ssh -L 3000:localhost:30002 brain_ai@192.168.68.56
# Then open: http://localhost:3000
```

**Solution 2:** Use server IP directly
```
http://192.168.68.56:30002
```

---

## 📊 How It All Works Together

```
You (User)
    ↓
Frontend (React UI) ← http://192.168.68.56:30002
    ↓
Gateway API ← http://192.168.68.56:30801
    ↓
19 Microservices (Running in K3s)
    ↓
AI Brain + Reasoning Engine
    ↓
Data Storage & External APIs
```

**Flow Example:**
1. You type message in frontend
2. Frontend sends to Gateway
3. Gateway routes to AI Brain
4. AI Brain processes with reasoning engine
5. Results sent back through Gateway
6. Frontend displays response

---

## 📜 Useful Commands

```bash
# Check all pods
kubectl get pods -n kilo-guardian

# View all services
kubectl get svc -n kilo-guardian

# View logs for a service
kubectl logs -n kilo-guardian -l app=kilo-frontend -f

# Restart the system
bash start-full-system.sh

# Run diagnostics
bash troubleshoot.sh

# Check specific pod details
kubectl describe pod <pod-name> -n kilo-guardian
```

---

## 🎯 What Should Happen

When everything is working:

1. **Frontend loads** - You see web interface
2. **AI responds** - Chat works, gets replies
3. **Notifications appear** - Updates from services
4. **Dashboard updates** - Real-time data
5. **Services integrate** - Reminders, finances, habits all sync

---

## Need Help?

Tell me:
1. What do you see when you open the frontend?
2. What errors (if any) appear?
3. What do you expect to happen but doesn't?
4. Are there specific features you want to use?

Then I can help debug the specific issue!
