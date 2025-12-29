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

cat <<'EOF'
Done. Next steps:
  - Install Prometheus stack via Helm into 'monitoring' namespace and configure to use k3s/prometheus-values.yaml
  - Replace REPLACE_ME tokens with actual gateway/admin token content (from /admin/tokens)
  - For air-gapped deployments, preload images into k3s containerd before applying manifests
EOF