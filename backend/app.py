from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.jobs import router as jobs_router
from backend.models.api import CapabilityResponse
from backend.services.capabilities import capabilities
from backend.services.dubbing import get_dubbing_provider


app = FastAPI(title="DubPatch API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs_router)


@app.on_event("startup")
def validate_dubbing_provider() -> None:
    """Fail clearly when an unimplemented automatic provider is selected."""
    get_dubbing_provider()


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
