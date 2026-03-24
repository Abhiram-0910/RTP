import requests
import json
import sys

BASE_URL = "http://localhost:8005"

def test_stats():
    print("Testing /api/stats...")
    try:
        resp = requests.get(f"{BASE_URL}/api/stats", timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Data: {json.dumps(resp.json(), indent=2)}")
    except Exception as e:
        print(f"Error testing stats: {e}")

def test_recommend():
    print("\nTesting /api/recommend...")
    # The endpoint expects the body to be the SearchRequest model if not wrapped, 
    # but based on my earlier 422 error, it seems it expects 'user_query' as a key.
    # I will try both if needed, but starting with the wrapped one that gave 422 'missing' earlier.
    payload = {"user_query": {"query": "haunting movie with dark humor"}}
    try:
        resp = requests.post(f"{BASE_URL}/api/recommend", json=payload, timeout=30)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"Found {len(results)} results.")
            for i, item in enumerate(results[:3]):
                title = item.get("media", {}).get("title", "Unknown")
                expl = item.get("explanation", "No explanation")
                print(f" {i+1}. {title}: {expl[:80]}...")
        else:
            print(f"Error: {resp.text}")
            # Try unwrapped if wrapped fails with 422
            if resp.status_code == 422:
                print("Retrying with unwrapped payload...")
                payload2 = {"query": "haunting movie with dark humor"}
                resp2 = requests.post(f"{BASE_URL}/api/recommend", json=payload2, timeout=30)
                print(f"Retry Status: {resp2.status_code}")
                if resp2.status_code == 200:
                    results = resp2.json().get("results", [])
                    print(f"Found {len(results)} results.")
    except Exception as e:
        print(f"Error testing recommend: {e}")

def test_similar():
    print("\nTesting /api/similar/598826...")
    try:
        resp = requests.get(f"{BASE_URL}/api/similar/598826", timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            results = resp.json()
            print(f"Found {len(results)} similar titles.")
            for i, item in enumerate(results[:3]):
                print(f" {i+1}. {item.get('title')}")
        else:
            print(f"Error: {resp.text}")
    except Exception as e:
        print(f"Error testing similar: {e}")

if __name__ == "__main__":
    test_stats()
    test_recommend()
    test_similar()
