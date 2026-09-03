"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import scheduler
from .api import auth_routes, data_routes, ingest_routes, settings_routes
from .db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("pulsevault")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    log.info("PulseVault backend ready")
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(title="PulseVault", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(auth_routes.router)
app.include_router(settings_routes.router)
app.include_router(data_routes.router)
app.include_router(ingest_routes.router)
