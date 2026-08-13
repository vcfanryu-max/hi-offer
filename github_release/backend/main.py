from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import generations, jobs, prompts, resumes, settings
from backend.config import CORS_ORIGINS, DEBUG_MODE
from backend.db import init_db
from backend.errors import UserFacingError



@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Resume Matcher Local API", version="2.5.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(UserFacingError)
async def user_error_handler(_request: Request, exc: UserFacingError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def validation_error_handler(_request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/api/health")
def health():
    return {"status": "ok", "storage": "local", "debug": DEBUG_MODE}


app.include_router(resumes.router)
app.include_router(jobs.router)
app.include_router(settings.router)
app.include_router(generations.router)
if DEBUG_MODE:
    app.include_router(prompts.router)
