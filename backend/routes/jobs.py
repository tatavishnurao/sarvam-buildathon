from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from backend.models.api import (
    ArtifactResponse,
    CorrectionRequest,
    CreateJobRequest,
    JobResponse,
)
from backend.services.job_service import JobService

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
service = JobService()


def _not_found(error: FileNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(request: CreateJobRequest) -> JobResponse:
    try:
        return service.create_job(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/upload", response_model=JobResponse)
async def upload(
    creator_authorised: Annotated[bool, Form()],
    target_language: Annotated[str, Form()] = "te-IN",
    source_language: Annotated[str, Form()] = "en-IN",
    expected_speakers: Annotated[int, Form()] = 2,
    job_id: Annotated[str | None, Form()] = None,
    source_file: Annotated[UploadFile | None, File()] = None,
    target_file: Annotated[UploadFile | None, File()] = None,
) -> JobResponse:
    try:
        if not creator_authorised:
            raise ValueError("Creator authorisation must be confirmed")
        if job_id is None:
            created = service.create_job(
                CreateJobRequest(
                    creator_authorised=True,
                    target_language=target_language,
                    source_language=source_language,
                    expected_speakers=expected_speakers,
                )
            )
            job_id = created.job_id
        return await service.save_upload(
            job_id, source_file=source_file, target_file=target_file
        )
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{job_id}/run", response_model=JobResponse)
def run_job(job_id: str, background_tasks: BackgroundTasks) -> JobResponse:
    try:
        state = service.get_state(job_id)
        if state["status"] not in {"created", "awaiting_dubbed_artifact", "failed", "complete"}:
            return JobResponse.model_validate(state)
        state.update(status="queued", progress=1, message="Review queued", error=None)
        service._store_state(state)
        background_tasks.add_task(service.run_job, job_id)
        return JobResponse.model_validate(state)
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    try:
        return JobResponse.model_validate(service.get_state(job_id))
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{job_id}/artifacts", response_model=ArtifactResponse)
def get_artifacts(job_id: str) -> ArtifactResponse:
    try:
        service.get_state(job_id)
        return ArtifactResponse(job_id=job_id, artifacts=service.artifacts(job_id))
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{job_id}/report")
def get_report(job_id: str) -> dict[str, object]:
    try:
        return service.report(job_id)
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/{job_id}/corrections", status_code=status.HTTP_201_CREATED)
def add_correction(job_id: str, correction: CorrectionRequest) -> dict[str, str]:
    try:
        service.add_correction(job_id, correction.model_dump(mode="json"))
        return {"status": "saved"}
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/{job_id}/patch")
def patch_audio(job_id: str) -> None:
    try:
        service.get_state(job_id)
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc
    raise HTTPException(
        status_code=409,
        detail="Audio regeneration is intentionally unavailable until review is stable",
    )
