from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.dependencies import get_session
from backend.services import resume_service


router = APIRouter(prefix="/api/resumes", tags=["resumes"])


@router.get("")
def get_versions(session: Session = Depends(get_session)):
    return {"items": resume_service.list_versions(session)}


@router.get("/current")
def get_current(session: Session = Depends(get_session)):
    current = resume_service.current_version(session)
    if not current:
        return {"item": None}
    items = resume_service.list_versions(session)
    return {"item": next(item for item in items if item["id"] == current.id)}


@router.post("/upload", status_code=201)
async def upload_resume(
    file: UploadFile = File(...), session: Session = Depends(get_session)
):
    raw = await file.read()
    return resume_service.upload_resume(
        session,
        filename=file.filename or "resume",
        raw=raw,
        mime_type=file.content_type,
    )


@router.patch("/versions/{version_id}/current")
def set_current(version_id: int, session: Session = Depends(get_session)):
    return resume_service.set_current(session, version_id)


@router.get("/versions/{version_id}/download")
def download_resume(version_id: int, session: Session = Depends(get_session)):
    path, filename, mime_type = resume_service.download_path(session, version_id)
    return FileResponse(path, filename=filename, media_type=mime_type)

