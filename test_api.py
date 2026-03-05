import requests, json

base = "http://localhost:8000"

tests = [
    {"label": "English query",  "query": "mind-bending sci-fi thriller"},
    {"label": "Hindi query",    "query": "koi acchi hindi comedy film"},
    {"label": "Telugu query",   "query": "Telugu lo manchi action cinema"},
]

for t in tests:
    print(f"\n=== {t['label']}: '{t['query']}' ===")
    r = requests.post(f"{base}/api/recommend",
        json={"query": t["query"], "user_id": "test_user"},
        timeout=30)
    if r.status_code == 200:
        data = r.json()
        movies = data.get("movies", [])
        print(f"  Results: {len(movies)}")
        print(f"  Language detected: {data.get('detected_language', 'N/A')}")
        print(f"  Translated: {data.get('translated_query', '(no translation)')}")
        print(f"  AI features: {data.get('ai_features', {})}")
        for m in movies[:3]:
            platforms = m.get('streaming_platforms', [])
            print(f"  - {m['title']} ({m.get('release_date','')[:4]}) | rating={m.get('rating')} | score={m.get('match_score')} | platforms={platforms[:2]}")
        print(f"  Explanation (first 150 chars): {data.get('explanation','')[:150]}")
    else:
        print(f"  ERROR {r.status_code}: {r.text[:200]}")
