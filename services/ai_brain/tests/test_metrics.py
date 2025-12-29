import requests
import os

def test_metrics_direct():
    url = os.environ.get('AI_BRAIN_URL', 'http://localhost:9004')
    r = requests.get(f"{url}/metrics")
    assert r.status_code == 200
    assert 'ai_brain_requests_total' in r.text


def test_metrics_via_gateway():
    gw = os.environ.get('GATEWAY_URL', 'http://localhost:8000')
    r = requests.get(f"{gw}/ai_brain/metrics")
    assert r.status_code == 200
    assert 'ai_brain_requests_total' in r.text
