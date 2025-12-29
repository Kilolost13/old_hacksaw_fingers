Kilo Guardian k3s deployment notes

Quick start (single-node K3s):

1. Install K3s (see https://k3s.io):
   curl -sfL https://get.k3s.io | sh -

2. Apply namespace, config and secrets:
   kubectl apply -f namespace.yaml
   kubectl apply -f secret-library-admin.yaml
   kubectl apply -f configmap.yaml

3. Apply core deployments / services (or apply per-service files):
   kubectl apply -f deployments-and-services.yaml

4. Install Prometheus (kube-prometheus-stack) via Helm and set `prometheus.values` to include `prometheus-values.yaml` or mount token file at `/etc/prometheus/secrets/gateway_admin_token`.

Air-gapped notes:
- Pre-pull and load images into k3s containerd: `ctr -n k8s.io images import <tar>` or `crictl` depending on runtime.
- Host `LIBRARY_ADMIN_KEY` as a Secret or via vault. Use `kubectl create secret generic library-admin --from-literal=LIBRARY_ADMIN_KEY=...`.

Expose & Ingress:
- Use an Ingress controller (traefik is bundled with k3s) or install nginx-ingress. Create an Ingress resource to route `/` to `kilo-frontend`.

Prometheus scraping:
- Prometheus should scrape `gateway:8000/admin/ai_brain/metrics` using a bearer token file.

Token creation & secret setup (recommended steps):
1. Create a persistent admin token (if needed):
   TOKEN=$(curl -s -X POST -H "X-Admin-Token: ${LIBRARY_ADMIN_KEY:-kilo-secure-admin-2024}" http://localhost:8000/admin/tokens | jq -r .token)
   # If the above returns null (tokens exist), use the first token from listing:
   if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then TOKEN=$(curl -s -H "X-Admin-Token: ${LIBRARY_ADMIN_KEY:-kilo-secure-admin-2024}" http://localhost:8000/admin/tokens | jq -r '.tokens[0].token'); fi

2. Save the token into a file and create a Kubernetes secret in the monitoring namespace:
   echo -n "$TOKEN" > prometheus-token.txt
   kubectl -n monitoring create secret generic gateway-admin-token --from-file=token=prometheus-token.txt

3. Use `k3s/prometheus-values.yaml` or ServiceMonitor to configure scraping and mount the token file into Prometheus.


Rolling upgrades and resilience:
- Use `kubectl rollout status deployment/kilo-gateway -n kilo-guardian` to monitor upgrades.
- Add PodDisruptionBudgets and HPAs as needed.
