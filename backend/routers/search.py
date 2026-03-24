"""
MIRAI — Search Router
=====================
Exposes POST /api/v1/search to the FastAPI application.
All errors are caught and returned as structured HTTPExceptions.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..recommendation_engine import search as run_search
from ..schemas import SearchRequest, SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Hybrid semantic movie & TV show recommendations",
    description=(
        "Accepts a natural-language query and returns up to 8 ranked "
        "recommendations using pgvector ANN search, hybrid scoring, "
        "MMR diversity re-ranking, and Gemini 1.5 Flash explanations."
    ),
)
async def search_endpoint(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """
    POST /api/v1/search

    Body: SearchRequest
    Returns: SearchResponse
    """
    try:
        return await run_search(request, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid search parameters: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unhandled error in /api/v1/search: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(exc)}",
        ) from exc
