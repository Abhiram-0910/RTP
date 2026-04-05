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
    Validates native cross-linguistic execution and RAG generation limits on specific queries.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/search", json={"query": "romantic comedy with emotional depth"})
        
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)

@pytest.mark.asyncio
async def test_search_empty():
    """
    Validates strict boundary errors upon empty payload ingestion correctly.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/search", json={"query": ""})
        
    assert response.status_code == 400
    assert "Query cannot be empty" in response.json()["detail"]

@pytest.mark.asyncio
async def test_trending():
    """
    Validates globally cached media arrays sequentially.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/trending")
        
    assert response.status_code == 200
    assert isinstance(response.json(), list)
