from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.jobs import router as jobs_router
from backend.models.api import CapabilityResponse
from backend.services.capabilities import capabilities
from backend.services.dubbing import get_dubbing_provider


DEFAULT_CORS_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
)


def cors_allowed_origins(value: str | None = None) -> list[str]:
    """Return explicit local-development origins, optionally overridden by env."""
    configured = value if value is not None else os.getenv("CORS_ALLOWED_ORIGINS")
    if not configured:
        return list(DEFAULT_CORS_ALLOWED_ORIGINS)
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Validate configured providers before accepting requests."""
    get_dubbing_provider()
    yield


app = FastAPI(title="DubPatch API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/capabilities", response_model=CapabilityResponse)
def get_capabilities() -> CapabilityResponse:
    return capabilities()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
