"""Health check endpoints."""

from fastapi import APIRouter

from src.agent.agent import is_mock_mode
from src.db.migrations import get_current_revision

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health() -> dict:
    """Health check endpoint."""
    try:
        revision = get_current_revision()
    except Exception:
        revision = None

    return {
        "status": "ok",
        "mock_mode": is_mock_mode(),
        "db_revision": revision,
    }
