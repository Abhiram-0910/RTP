import pytest
from httpx import AsyncClient, ASGITransport
from backend.enhanced_main import app

@pytest.mark.asyncio
async def test_health():
    """
    Validates API runtime health probe dynamically tracking structural uptime bounds cleanly.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health")
    
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_search_valid():
    """
    Validates cross-linguistic search with the production /api/recommend endpoint.
    """
    payload = {
        "query": "romantic comedy with emotional depth",
        "user_id": "test_user",
        "media_type": "movie",
        "language_preference": "en"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/recommend", json=payload)
        
    assert response.status_code == 200
    data = response.json()
    assert "movies" in data
    assert isinstance(data["movies"], list)

@pytest.mark.asyncio
async def test_search_empty():
    """
    Validates boundary error enforcement on empty queries.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/recommend", json={"query": ""})
        
    assert response.status_code == 400
    assert "Query cannot be empty" in response.json()["detail"]

@pytest.mark.asyncio
async def test_trending():
    """
    Validates trending media aggregation and explanation generation structure.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/trending")
        
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "trending" in data
    assert "explanation" in data
    assert isinstance(data["trending"], list)
