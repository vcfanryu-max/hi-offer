from __future__ import annotations

import json
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.ai.schemas import GenerationRequest
from backend.dependencies import get_key_store, get_session
from backend.security import ApiKeyStore
from backend.services import export_service, generation_service


router = APIRouter(prefix="/api/generations", tags=["generations"])


def _download_header(filename: str) -> str:
    ascii_fallback = "".join(char if ord(char) < 128 else "_" for char in filename)
    ascii_fallback = ascii_fallback.replace('"', "_") or "Resume_Matcher_Download"
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"


@router.get("")
def list_items(session: Session = Depends(get_session)):
    return {"items": generation_service.list_generations(session)}


@router.get("/{generation_id}")
def get_item(generation_id: int, session: Session = Depends(get_session)):
    return generation_service.public_generation(
        generation_service.get_generation(session, generation_id)
    )


@router.post("", status_code=201)
async def create_item(
    payload: GenerationRequest,
    session: Session = Depends(get_session),
    store: ApiKeyStore = Depends(get_key_store),
):
    return await generation_service.create_generation(
        session,
        store,
        resume_version_id=payload.resume_version_id,
        job_id=payload.job_id,
    )


@router.post("/{generation_id}/retry/{module}")
async def retry_item(
    generation_id: int,
    module: str,
    session: Session = Depends(get_session),
    store: ApiKeyStore = Depends(get_key_store),
):
    return await generation_service.retry_module(session, store, generation_id, module)


@router.get("/{generation_id}/export/{kind}")
def export_item(generation_id: int, kind: str, session: Session = Depends(get_session)):
    item = generation_service.get_generation(session, generation_id)
    if kind == "hr-message" and item.hr_message_json:
        text = export_service.hr_text(json.loads(item.hr_message_json))
        filename, media = f"Resume_Matcher_HR_Message_{item.id}.txt", "text/plain; charset=utf-8"
    elif kind == "resume-advice" and item.resume_advice_json:
        text = export_service.advice_markdown(
            json.loads(item.resume_advice_json),
            company=item.job.company,
            position=item.job.position,
            resume_version=item.resume_version.version_number,
            created_at=item.created_at,
        )
        filename, media = f"Resume_Matcher_Resume_Advice_{item.id}.md", "text/markdown; charset=utf-8"
    elif kind == "match" and item.match_result_json:
        text = export_service.match_markdown(json.loads(item.match_result_json))
        filename, media = f"Resume_Matcher_Match_{item.id}.md", "text/markdown; charset=utf-8"
    elif kind == "generation":
        text = export_service.generation_markdown(
            jd_text=item.job.jd_text,
            match=json.loads(item.match_result_json) if item.match_result_json else None,
            hr_message=json.loads(item.hr_message_json) if item.hr_message_json else None,
            resume_advice=json.loads(item.resume_advice_json) if item.resume_advice_json else None,
            company=item.job.company, position=item.job.position,
            resume_version=item.resume_version.version_number, created_at=item.created_at,
        )
        stem = export_service.safe_export_stem(item.job.position, fallback=f"Generation_{item.id}")
        filename, media = f"{stem}_{item.created_at.date().isoformat()}.md", "text/markdown; charset=utf-8"
    else:
        return Response("该模块尚无可下载结果。", status_code=404)
    return Response(
        text.encode("utf-8-sig"),
        media_type=media,
        headers={"Content-Disposition": _download_header(filename)},
    )
