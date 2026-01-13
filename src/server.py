"""FastAPI server for the shipping agent."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup/shutdown."""
    from src.agent.agent import is_mock_mode
    from src.db.migrations import run_migrations
    from src.db.seed import seed_demo_data, has_demo_data
    from src.db.database import get_db_session
    from src.api.chat import agents

    logger.info("Running database migrations...")
    try:
        run_migrations()
        logger.info("Migrations complete")
    except Exception as e:
        logger.error("Migration failed: %s", e)

    if is_mock_mode():
        with get_db_session() as db:
            if not has_demo_data(db):
                logger.info("Seeding demo data...")
                seed_demo_data(db)
                logger.info("Demo data seeded")

    mode = "MOCK" if is_mock_mode() else "LIVE"
    print(f"\n  Shipping Agent Server ({mode} MODE)")
    print(f"  http://localhost:8000\n")

    yield

    agents.clear()


app = FastAPI(
    title="Shipping Agent",
    description="AI-powered shipping assistant",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
from src.api.health import router as health_router
from src.api.auth import router as auth_router
from src.api.chat import router as chat_router
from src.api.orders import router as orders_router
from src.api.shipping import router as shipping_router
from src.api.webhooks import router as webhooks_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(orders_router)
app.include_router(shipping_router)
app.include_router(webhooks_router)


# Static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main chat UI."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(
        content="<h1>Shipping Agent</h1><p>Static files not found. Run from project root.</p>",
        status_code=200,
    )


def main():
    """Run the server."""
    import uvicorn
    uvicorn.run(
        "src.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
