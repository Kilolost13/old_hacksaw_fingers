#!/bin/bash
# Kilo Guardian - Interactive Troubleshooting Guide

set -e
source venv/bin/activate

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Kilo Guardian - System Troubleshooter                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo

# Test 1: Frontend
echo "TEST 1: Frontend Access"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Testing: http://192.168.68.56:30002"
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://192.168.68.56:30002 2>&1)
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo "✅ Frontend is responding with HTTP 200"
else
    echo "⚠️  Frontend returned: HTTP $FRONTEND_STATUS"
fi
echo

# Test 2: Gateway
echo "TEST 2: Gateway API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Testing: http://192.168.68.56:30801/health"
if curl -s http://192.168.68.56:30801/health | grep -q "ok"; then
    echo "✅ Gateway API is responding"
    curl -s http://192.168.68.56:30801/health | python3 -m json.tool
else
    echo "❌ Gateway API not responding properly"
fi
echo

# Test 3: Agent API
echo "TEST 3: Agent API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Testing: http://localhost:9100/agent/status"
if curl -s http://localhost:9100/agent/status | grep -q "ok"; then
    echo "✅ Agent API is responding"
    curl -s http://localhost:9100/agent/status | python3 -m json.tool
else
    echo "❌ Agent API not responding"
fi
echo

# Test 4: Microservices
echo "TEST 4: Kubernetes Microservices"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
RUNNING=$(kubectl get pods -n kilo-guardian --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
TOTAL=$(kubectl get pods -n kilo-guardian --no-headers 2>/dev/null | wc -l)
echo "Running Pods: $RUNNING / $TOTAL"
if [ "$RUNNING" -ge 15 ]; then
    echo "✅ Most microservices are running"
else
    echo "⚠️  Only $RUNNING pods running. Some services may be down."
fi

echo
echo "Pods by status:"
kubectl get pods -n kilo-guardian --no-headers | awk '{print $3}' | sort | uniq -c
echo

# Test 5: Processes
echo "TEST 5: Local Processes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ps aux | grep -q "kilo_agent_api.py" | grep -v grep; then
    echo "✅ Agent API process is running"
else
    echo "❌ Agent API process not found"
fi

if ps aux | grep -q "kilo_proactive_agent.py" | grep -v grep; then
    echo "✅ Proactive Agent process is running"
else
    echo "❌ Proactive Agent process not found"
fi
echo

# Test 6: Service Accessibility
echo "TEST 6: K3s Services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Available services:"
kubectl get svc -n kilo-guardian -o wide | head -10
echo "... (showing first 10)"
echo

# Summary
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  NEXT STEPS                                                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo
echo "1️⃣  If Frontend test FAILED:"
echo "    → Check: kubectl logs -n kilo-guardian -l app=kilo-frontend"
echo "    → Try: kubectl rollout restart deployment/kilo-frontend -n kilo-guardian"
echo
echo "2️⃣  If Gateway test FAILED:"
echo "    → Check: kubectl logs -n kilo-guardian -l app=kilo-gateway"
echo "    → Try: kubectl rollout restart deployment/kilo-gateway -n kilo-guardian"
echo
echo "3️⃣  If Agent API test FAILED:"
echo "    → Check: ps aux | grep kilo_agent_api"
echo "    → Try: pkill -f kilo_agent_api && python3 kilo_agent_api.py &"
echo
echo "4️⃣  If Microservices count is LOW:"
echo "    → Check specific pod: kubectl describe pod <pod-name> -n kilo-guardian"
echo "    → View logs: kubectl logs -n kilo-guardian -l app=<service>"
echo
echo "📱 WHAT TO TEST MANUALLY:"
echo "   1. Open http://192.168.68.56:30002 in browser"
echo "   2. Try to send a message or interact with the UI"
echo "   3. Report what you see/don't see"
echo
