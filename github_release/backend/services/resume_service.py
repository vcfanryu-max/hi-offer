from __future__ import annotations

import json
from mimetypes import guess_type

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.config import RESUME_DIR
from backend.config import DEBUG_MODE
from backend.db.models import Resume, ResumeVersion
from backend.errors import NotFoundError
from backend.parsers import parse_document
from backend.services.files import resolve_stored_file, store_file


def _public(version: ResumeVersion, *, current_id: int | None) -> dict:
    return {
        "id": version.id,
        "resume_id": version.resume_id,
        "version_number": version.version_number,
        "label": f"Resume V{version.version_number}",
        "original_filename": version.original_filename,
        "mime_type": version.mime_type,
        "source_type": version.source_type or "file",
        "parser_method": version.parser_method,
        "ocr_used": bool(version.ocr_used),
        "ocr_metadata": json.loads(version.ocr_metadata_json) if version.ocr_metadata_json else {},
        "is_current": version.id == current_id,
        "created_at": version.created_at.isoformat(),
    }


def list_versions(session: Session) -> list[dict]:
    resume = session.scalar(select(Resume).order_by(Resume.id).limit(1))
    if not resume:
        return []
    versions = session.scalars(
        select(ResumeVersion)
        .where(ResumeVersion.resume_id == resume.id)
        .order_by(ResumeVersion.version_number.desc())
    ).all()
    return [_public(item, current_id=resume.current_version_id) for item in versions]


def current_version(session: Session) -> ResumeVersion | None:
    resume = session.scalar(select(Resume).order_by(Resume.id).limit(1))
    if not resume or not resume.current_version_id:
        return None
    return session.get(ResumeVersion, resume.current_version_id)


def upload_resume(session: Session, *, filename: str, raw: bytes, mime_type: str | None) -> dict:
    parsed = parse_document(filename=filename, raw=raw, kind="resume")
    resume = session.scalar(select(Resume).order_by(Resume.id).limit(1))
    if not resume:
        resume = Resume(name="我的简历")
        session.add(resume)
        session.flush()
    number = session.scalar(
        select(func.max(ResumeVersion.version_number)).where(ResumeVersion.resume_id == resume.id)
    ) or 0
    path = store_file(RESUME_DIR, filename, raw)
    version = ResumeVersion(
        resume_id=resume.id,
        version_number=number + 1,
        original_filename=filename,
        mime_type=mime_type or guess_type(filename)[0] or "application/octet-stream",
        file_path=str(path),
        parsed_text=parsed.text,
        source_type=parsed.source_type,
        parser_method=parsed.method,
        ocr_used=parsed.ocr_used,
        ocr_metadata_json=json.dumps(parsed.ocr_metadata, ensure_ascii=False),
        ocr_text=parsed.ocr_text or None,
    )
    session.add(version)
    session.flush()
    resume.current_version_id = version.id
    session.commit()
    payload = {**_public(version, current_id=version.id), "warnings": list(parsed.warnings)}
    if DEBUG_MODE and parsed.ocr_used:
        payload["ocr_extracted_text"] = parsed.ocr_text
    return payload


def set_current(session: Session, version_id: int) -> dict:
    version = session.get(ResumeVersion, version_id)
    if not version:
        raise NotFoundError("找不到该简历版本。")
    resume = session.get(Resume, version.resume_id)
    assert resume is not None
    resume.current_version_id = version.id
    session.commit()
    return _public(version, current_id=version.id)


def get_version(session: Session, version_id: int) -> ResumeVersion:
    version = session.get(ResumeVersion, version_id)
    if not version:
        raise NotFoundError("找不到该简历版本。")
    return version


def download_path(session: Session, version_id: int):
    version = get_version(session, version_id)
    return resolve_stored_file(RESUME_DIR, version.file_path), version.original_filename, version.mime_type
