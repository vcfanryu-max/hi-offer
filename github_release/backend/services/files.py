from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from backend.errors import NotFoundError


SAFE_NAME = re.compile(r"[^\w.\-（）()\u4e00-\u9fff]+", re.UNICODE)


def sanitise_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = SAFE_NAME.sub("_", name)[:180]
    return name or "document"


def store_file(directory: Path, filename: str, raw: bytes) -> Path:
    safe_name = sanitise_filename(filename)
    path = (directory / f"{uuid4().hex}_{safe_name}").resolve()
    if directory.resolve() not in path.parents:
        raise ValueError("Invalid storage path")
    path.write_bytes(raw)
    return path


def resolve_stored_file(directory: Path, value: str | None) -> Path:
    if not value:
        raise NotFoundError("没有可下载的原始文件。")
    path = Path(value).resolve()
    if directory.resolve() not in path.parents or not path.is_file():
        raise NotFoundError("原始文件不存在或已被移动。")
    return path

