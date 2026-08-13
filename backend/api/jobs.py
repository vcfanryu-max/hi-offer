from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from backend.ai.schemas import JobTextInput
from backend.dependencies import get_session
from backend.services import job_service


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def get_jobs(session: Session = Depends(get_session)):
    return {"items": job_service.list_jobs(session)}


@router.get("/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)):
    return job_service.public_job(job_service.get_job(session, job_id))


@router.post("/text", status_code=201)
def create_text(payload: JobTextInput, session: Session = Depends(get_session)):
    return job_service.create_text(
        session,
        jd_text=payload.jd_text,
        company=payload.company,
        position=payload.position,
    )


@router.post("/upload", status_code=201)
async def upload_job(file: UploadFile = File(...), session: Session = Depends(get_session)):
    raw = await file.read()
    return job_service.upload_job(
        session,
        filename=file.filename or "job",
        raw=raw,
        mime_type=file.content_type,
    )


@router.get("/{job_id}/download")
def download_job(job_id: int, session: Session = Depends(get_session)):
    source, filename, mime_type = job_service.download(session, job_id)
    if isinstance(source, bytes):
        return Response(
            source,
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return FileResponse(source, filename=filename, media_type=mime_type)

