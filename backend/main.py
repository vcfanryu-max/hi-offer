from __future__ import annotations

from contextlib import asynccontextmanager
import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import generations, jobs, prompts, resumes, settings
from backend.config import ACCESS_TOKEN, CORS_ORIGINS, DEBUG_MODE
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
    allow_headers=["Content-Type", "X-Access-Token"],
)


@app.middleware("http")
async def require_access_token(request: Request, call_next):
    """Protect deployed API data while keeping local development frictionless."""
    if (
        ACCESS_TOKEN
        and request.url.path.startswith("/api/")
        and request.url.path != "/api/health"
        and request.method != "OPTIONS"
    ):
        # Query auth is limited to browser download links, which cannot attach
        # a custom header. Normal API requests use X-Access-Token.
        supplied = request.headers.get("X-Access-Token", "") or request.query_params.get("access_token", "")
        if not secrets.compare_digest(supplied, ACCESS_TOKEN):
            return JSONResponse(status_code=401, content={"detail": "访问密码不正确。"})
    return await call_next(request)


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
