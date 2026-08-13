from __future__ import annotations

import json
from mimetypes import guess_type

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import DEBUG_MODE, JOB_DIR
from backend.db.models import Job
from backend.errors import NotFoundError
from backend.parsers import parse_document, parse_text
from backend.services.files import resolve_stored_file, store_file


def _title_fallback(text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    position = next((line[:120] for line in lines if any(k in line for k in ("岗位", "职位", "工程师", "产品", "运营", "设计"))), "未命名岗位")
    return "", position


def public_job(job: Job) -> dict:
    return {
        "id": job.id,
        "company": job.company or "未注明公司",
        "position": job.position or "未命名岗位",
        "source_type": job.source_type,
        "parser_method": job.parser_method,
        "ocr_used": bool(job.ocr_used),
        "ocr_metadata": json.loads(job.ocr_metadata_json) if job.ocr_metadata_json else {},
        "original_filename": job.original_filename,
        "jd_text": job.jd_text,
        "created_at": job.created_at.isoformat(),
    }


def create_text(session: Session, *, jd_text: str, company: str = "", position: str = "") -> dict:
    parsed = parse_text(jd_text, kind="job")
    inferred_company, inferred_position = _title_fallback(parsed.text)
    job = Job(
        company=company or inferred_company,
        position=position or inferred_position,
        source_type="text",
        jd_text=parsed.text,
        parser_method=parsed.method,
        ocr_used=False,
        ocr_metadata_json="{}",
        ocr_text=None,
    )
    session.add(job)
    session.commit()
    return public_job(job)


def upload_job(session: Session, *, filename: str, raw: bytes, mime_type: str | None) -> dict:
    parsed = parse_document(filename=filename, raw=raw, kind="job")
    company, position = _title_fallback(parsed.text)
    path = store_file(JOB_DIR, filename, raw)
    job = Job(
        company=company,
        position=position,
        source_type=parsed.source_type,
        original_filename=filename,
        mime_type=mime_type or guess_type(filename)[0] or "application/octet-stream",
        file_path=str(path),
        jd_text=parsed.text,
        parser_method=parsed.method,
        ocr_used=parsed.ocr_used,
        ocr_metadata_json=json.dumps(parsed.ocr_metadata, ensure_ascii=False),
        ocr_text=parsed.ocr_text or None,
    )
    session.add(job)
    session.commit()
    payload = {**public_job(job), "warnings": list(parsed.warnings)}
    if DEBUG_MODE and parsed.ocr_used:
        payload["ocr_extracted_text"] = parsed.ocr_text
    return payload


def get_job(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise NotFoundError("找不到该岗位记录。")
    return job


def list_jobs(session: Session) -> list[dict]:
    jobs = session.scalars(select(Job).order_by(Job.created_at.desc())).all()
    return [public_job(item) for item in jobs]


def download(session: Session, job_id: int):
    job = get_job(session, job_id)
    if job.source_type == "text":
        return job.jd_text.encode("utf-8"), f"JD_{job.id}.txt", "text/plain; charset=utf-8"
    path = resolve_stored_file(JOB_DIR, job.file_path)
    return path, job.original_filename or f"JD_{job.id}", job.mime_type or "application/octet-stream"
