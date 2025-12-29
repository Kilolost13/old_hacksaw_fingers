#!/usr/bin/env bash
set -euo pipefail

NS=kilo-guardian

echo "Applying namespace and base config..."
kubectl apply -f k3s/namespace.yaml
kubectl apply -f k3s/secret-library-admin.yaml -n ${NS}
kubectl apply -f k3s/configmap.yaml -n ${NS}

echo "Applying core deployments and services..."
kubectl apply -f k3s/deployments-and-services.yaml -n ${NS}
kubectl apply -f k3s/more-services.yaml -n ${NS}

echo "Applying PDBs and HPAs..."
kubectl apply -f k3s/pdbs-and-hpas.yaml -n ${NS}

echo "Applying Ingress..."
kubectl apply -f k3s/ingress.yaml -n ${NS}

echo "Creating placeholder service account secrets for Prometheus scraping (fill in token files manually for air-gapped)..."
# Create placeholder secrets - update token values with actual tokens
kubectl -n monitoring create secret generic gateway-admin-token --from-literal=token=REPLACE_ME || true
kubectl -n monitoring create secret generic ai-brain-metrics-token --from-literal=token=REPLACE_ME || true

# If a token file exists locally, create the secret from it (useful for automated flows)
if [ -f "k3s/prometheus-token.txt" ]; then
  echo "Found k3s/prometheus-token.txt — creating gateway-admin-token secret in 'monitoring' namespace"
  kubectl -n monitoring create secret generic gateway-admin-token --from-file=token=k3s/prometheus-token.txt --dry-run=client -o yaml | kubectl apply -f - || true
fi

# Install Prometheus stack via Helm if helm is available
if command -v helm >/dev/null 2>&1; then
  echo "Helm detected — installing kube-prometheus-stack into 'monitoring' namespace (if not present)"
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts || true
  helm repo update || true
  helm upgrade --install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace -f k3s/prometheus-values.yaml || true
else
  echo "Helm not found; skipping helm install. Install helm and then run: helm upgrade --install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace -f k3s/prometheus-values.yaml"
fi

cat <<'EOF'
Done. Next steps:
  - If helm was not installed, install helm and re-run this script to deploy Prometheus.
  - Ensure gateway-admin-token secret contains the actual token value (k3s/prometheus-token.txt) for scraping.
  - For air-gapped deployments, preload images into k3s containerd before applying manifests
EOF