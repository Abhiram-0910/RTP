import requests
import json

base_url = "http://localhost:8000"

print("--- Testing /api/recommend ---")
payload = {"query": "something haunting with unexpected dark humor"}
try:
    resp = requests.post(f"{base_url}/api/recommend", json=payload)
    print(f"Sent body: {resp.request.body}")
    print(f"Status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2)[:500])
except Exception as e:
    print(f"Error: {e}")

print("\n--- Testing /api/similar/524288 ---")
try:
    resp = requests.get(f"{base_url}/api/similar/524288")
    print(f"Status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2)[:500])
except Exception as e:
    print(f"Error: {e}")
