from __future__ import annotations

import re
from pathlib import Path


PROMPT_ROOT = Path(__file__).resolve().parent
TOKEN_PATTERN = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")
VERSION_PATTERN = re.compile(r"v([1-9][0-9]*)")
TASKS = frozenset({
    "resume_structure",
    "jd_analysis",
    "match_analysis",
    "hr_message",
    "resume_advice",
    "structured_repair",
})


def load_prompt(task: str, version: str) -> str:
    if task not in TASKS or not VERSION_PATTERN.fullmatch(version):
        raise FileNotFoundError("Prompt 任务或版本无效。")
    path = PROMPT_ROOT / task / f"{version}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt 不存在：{task}/{version}")
    return path.read_text(encoding="utf-8").strip()


def load_role() -> str:
    return (PROMPT_ROOT / "role.md").read_text(encoding="utf-8").strip()


def list_versions(task: str) -> list[str]:
    if task not in TASKS:
        return []
    task_dir = PROMPT_ROOT / task
    if not task_dir.is_dir():
        return []
    versions = [
        path.stem
        for path in task_dir.glob("v*.md")
        if path.is_file() and VERSION_PATTERN.fullmatch(path.stem)
    ]
    return sorted(versions, key=lambda value: int(VERSION_PATTERN.fullmatch(value).group(1)))


def render_prompt(task: str, version: str, **values: str) -> str:
    template = load_prompt(task, version)
    missing = set(TOKEN_PATTERN.findall(template)).difference(values)
    if missing:
        raise ValueError(f"Prompt 缺少变量：{', '.join(sorted(missing))}")
    return TOKEN_PATTERN.sub(lambda match: values[match.group(1)], template)
