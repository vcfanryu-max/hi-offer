from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.ai.pipeline import ResumeMatcherPipeline
from backend.ai.prompts.loader import list_versions, load_prompt
from backend.dependencies import get_key_store, get_session
from backend.security import ApiKeyStore
from backend.services import api_config_service, job_service, resume_service


router = APIRouter(prefix="/api/dev/prompts", tags=["developer"])
RUNNABLE_TASKS = ("resume_structure", "jd_analysis", "match_analysis", "hr_message", "resume_advice")
ALL_TASKS = (*RUNNABLE_TASKS, "structured_repair")


class PromptRunInput(BaseModel):
    task: Literal["resume_structure", "jd_analysis", "match_analysis", "hr_message", "resume_advice"]
    prompt_version: str = Field(default="v1", pattern=r"^v[1-9][0-9]*$")
    resume_version_id: int
    job_id: int
    temperature: float = Field(default=0.2, ge=0, le=1)


@router.get("")
def prompt_catalog():
    return {"tasks": [{
        "id": task, "versions": list_versions(task),
        "content": load_prompt(task, list_versions(task)[-1]),
        "runnable": task in RUNNABLE_TASKS,
    } for task in ALL_TASKS]}


@router.post("/run")
async def run_prompt(payload: PromptRunInput, session: Session = Depends(get_session),
                     store: ApiKeyStore = Depends(get_key_store)):
    resume_record = resume_service.get_version(session, payload.resume_version_id)
    job_record = job_service.get_job(session, payload.job_id)
    pipeline = ResumeMatcherPipeline(api_config_service.make_client(session, store))
    started = time.perf_counter()
    resume_result = await pipeline.resume_structure(
        resume_record.parsed_text,
        version=payload.prompt_version if payload.task == "resume_structure" else "v1",
        temperature=payload.temperature if payload.task == "resume_structure" else 0.1,
    )
    if payload.task == "resume_structure":
        result = resume_result
    else:
        jd_result = await pipeline.jd_analysis(
            job_record.jd_text,
            version=payload.prompt_version if payload.task == "jd_analysis" else "v1",
            temperature=payload.temperature if payload.task == "jd_analysis" else 0.1,
        )
        if payload.task == "jd_analysis":
            result = type("DevResult", (), {"value": jd_result.value, "trace": jd_result.traces[-1]})()
        else:
            match_result = await pipeline.match_analysis(
                resume_result.value,
                jd_result.value,
                version=payload.prompt_version if payload.task == "match_analysis" else "v2",
                temperature=payload.temperature if payload.task == "match_analysis" else 0.2,
            )
            if payload.task == "match_analysis":
                result = match_result
            elif payload.task == "hr_message":
                result = await pipeline.hr_message(resume_result.value, jd_result.value, match_result.value,
                                                   version=payload.prompt_version, temperature=payload.temperature)
            else:
                result = await pipeline.resume_advice(resume_result.value, jd_result.value, match_result.value,
                                                     version=payload.prompt_version, temperature=payload.temperature)
    trace = result.trace.public_dict()
    config = api_config_service.get_record(session)
    return {
        "prompt_content": load_prompt(payload.task, payload.prompt_version),
        "raw_output": trace["raw_output"], "parsed_output": result.value.model_dump(),
        "normalized_output": trace["normalized_json"], "validation_error": trace["validation_errors"],
        "request_id": trace["request_id"], "repair_attempted": trace["repair_attempted"],
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "model": config.model if config else "", "prompt_version": payload.prompt_version,
    }
