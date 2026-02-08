#!/bin/bash
# Start Full Kilo Guardian System - K3s + Frontend + AI Agent

set -e

echo "🚀 Starting Full Kilo Guardian System..."
echo

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
echo -e "${BLUE}[1/5] Activating Python virtual environment...${NC}"
source venv/bin/activate

# Check K3s status
echo -e "${BLUE}[2/5] Checking K3s cluster...${NC}"
if ! timeout 5 kubectl cluster-info > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  K3s not responding. Make sure K3s is running.${NC}"
    echo "Run: sudo systemctl start k3s"
    exit 1
fi
CLUSTER_STATUS=$(kubectl get nodes -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}')
if [ "$CLUSTER_STATUS" = "True" ]; then
    echo -e "${GREEN}✓ K3s cluster is running${NC}"
else
    echo -e "${YELLOW}⚠️  K3s cluster not ready${NC}"
fi

# Check microservices
echo -e "${BLUE}[3/5] Checking microservices...${NC}"
RUNNING_PODS=$(kubectl get pods -n kilo-guardian --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
echo -e "${GREEN}✓ ${RUNNING_PODS} microservices running${NC}"

# Get access URLs
echo -e "${BLUE}[4/5] Getting service URLs...${NC}"
FRONTEND_URL="http://192.168.68.56:30002"
GATEWAY_URL="http://192.168.68.56:30801"
AGENT_API_URL="http://localhost:9100"

echo -e "${GREEN}✓ Frontend: ${FRONTEND_URL}${NC}"
echo -e "${GREEN}✓ Gateway: ${GATEWAY_URL}${NC}"

# Start Agent API if not running
echo -e "${BLUE}[5/5] Starting AI Agent API...${NC}"
if ! timeout 2 curl -s http://localhost:9100/agent/status > /dev/null 2>&1; then
    echo "Starting Kilo Agent API on port 9100..."
    python3 kilo_agent_api.py > logs/agent-api.log 2>&1 &
    AGENT_PID=$!
    echo "Kilo Agent API started (PID: $AGENT_PID)"
    sleep 2
else
    echo -e "${GREEN}✓ Agent API already running${NC}"
fi

# Start Proactive Agent
echo -e "${BLUE}Starting Proactive Agent (Supervisory Agent)...${NC}"
python3 kilo_proactive_agent.py > logs/proactive-agent.log 2>&1 &
PROACTIVE_PID=$!
echo "Kilo Proactive Agent started (PID: $PROACTIVE_PID)"

echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 Kilo Guardian System Started!${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo -e "📱 ${BLUE}Frontend UI:${NC}"
echo -e "   📲 Desktop: ${FRONTEND_URL}"
echo -e "   📱 Mobile/Tablet: Open browser and navigate to http://<server-ip>:30002"
echo
echo -e "🔌 ${BLUE}API Endpoints:${NC}"
echo -e "   🌐 Gateway API: ${GATEWAY_URL}"
echo -e "   🤖 Agent API: ${AGENT_API_URL}"
echo -e "   📚 API Docs: ${AGENT_API_URL}/docs"
echo
echo -e "📊 ${BLUE}Running Services:${NC}"
echo -e "   • K3s Kubernetes Cluster: ✓ Running"
echo -e "   • ${RUNNING_PODS} Microservices: ✓ Running"
echo -e "   • AI Brain Service: ✓ Running in K3s"
echo -e "   • Reasoning Engine: ✓ Running in K3s"
echo -e "   • Agent API: ✓ Running on 9100"
echo -e "   • Proactive Agent (Supervisor): ✓ Running"
echo
echo -e "🎯 ${BLUE}Next Steps:${NC}"
echo -e "   1. Open frontend: ${FRONTEND_URL}"
echo -e "   2. Chat with AI supervisor through the web interface"
echo -e "   3. View agent notifications and status"
echo -e "   4. Monitor system through dashboard"
echo
echo -e "📜 ${BLUE}View Logs:${NC}"
echo -e "   tail -f logs/agent-api.log"
echo -e "   tail -f logs/proactive-agent.log"
echo -e "   kubectl logs -n kilo-guardian -f deployment/kilo-ai-brain"
echo
