from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEBUG_MODE = os.getenv("DEBUG", "").strip().casefold() in {"1", "true", "yes", "on"}
DATA_DIR = Path(os.getenv("RESUME_MATCHER_DATA_DIR", PROJECT_ROOT / "data")).resolve()
DATABASE_PATH = DATA_DIR / "app.db"
RESUME_DIR = DATA_DIR / "resumes"
JOB_DIR = DATA_DIR / "jobs"
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
API_KEY_SERVICE = "resume-matcher-local"

_default_cors_origins = "http://localhost:3000,http://127.0.0.1:3000"
CORS_ORIGINS = tuple(
    origin.strip().rstrip("/")
    for origin in os.getenv("RESUME_MATCHER_CORS_ORIGINS", _default_cors_origins).split(",")
    if origin.strip()
)

for directory in (DATA_DIR, RESUME_DIR, JOB_DIR):
    directory.mkdir(parents=True, exist_ok=True)


PROVIDERS: dict[str, dict[str, str]] = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-5-mini",
    },
    "Custom": {
        "base_url": "",
        "default_model": "",
    },
}


RESUME_STRUCTURE_PROMPT_VERSION = "v1"
JD_ANALYSIS_PROMPT_VERSION = "v1"
MATCH_PROMPT_VERSION = "v2"
HR_PROMPT_VERSION = "v2"
RESUME_ADVICE_PROMPT_VERSION = "v2"
STRUCTURED_REPAIR_PROMPT_VERSION = "v1"

# Conservative context budgets. They are intentionally below provider-advertised
# maxima so the system prompt, JSON Schema and output all retain headroom.
MODEL_CONTEXT_WINDOWS = {
    "deepseek-chat": 64_000,
    "deepseek-reasoner": 64_000,
    "gpt-5-mini": 128_000,
}
DEFAULT_CONTEXT_WINDOW = 32_000
MAX_SAFE_JD_INPUT_TOKENS = 24_000
