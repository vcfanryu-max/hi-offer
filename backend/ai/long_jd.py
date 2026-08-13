from __future__ import annotations

import math
import re
from dataclasses import dataclass

from backend.ai.schemas import JDAnalysis
from backend.config import DEFAULT_CONTEXT_WINDOW, MAX_SAFE_JD_INPUT_TOKENS, MODEL_CONTEXT_WINDOWS


@dataclass(frozen=True)
class LongJDDiagnostics:
    original_chars: int
    estimated_tokens: int
    long_jd_triggered: bool
    chunk_count: int
    final_structured_jd_size: int = 0

    def as_dict(self) -> dict:
        return {
            "jd_original_chars": self.original_chars,
            "estimated_tokens": self.estimated_tokens,
            "long_jd_triggered": self.long_jd_triggered,
            "chunk_count": self.chunk_count,
            "final_structured_jd_size": self.final_structured_jd_size,
        }


def estimate_tokens(text: str) -> int:
    """Conservative tokenizer-free estimate for mixed Chinese and Latin text."""
    cjk = len(re.findall(r"[\u3400-\u9fff\uf900-\ufaff]", text))
    other = max(0, len(text) - cjk)
    return cjk + math.ceil(other / 3.5)


def safe_jd_budget(model: str) -> int:
    context = MODEL_CONTEXT_WINDOWS.get(model.casefold(), DEFAULT_CONTEXT_WINDOW)
    return max(4_000, min(MAX_SAFE_JD_INPUT_TOKENS, int(context * 0.45)))


def semantic_chunks(text: str, *, token_budget: int) -> list[str]:
    """Split on headings/paragraphs while preserving every non-whitespace character."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    if len(blocks) == 1:
        blocks = [line.strip() for line in normalized.splitlines() if line.strip()]
    chunks: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            chunks.append("\n\n".join(current))
            current.clear()

    for block in blocks:
        if estimate_tokens(block) > token_budget:
            flush()
            # A single huge paragraph still has to be preserved. Split it at
            # sentence punctuation first and then by a conservative char window.
            sentences = [part for part in re.split(r"(?<=[。！？；.!?;])", block) if part]
            # One CJK character is conservatively counted as one token, so a
            # character window no larger than the token budget is safe for
            # both Chinese and Latin text under estimate_tokens().
            char_window = max(1, token_budget)
            # Preserve semantic sentence boundaries first. A pathological
            # sentence that exceeds the budget is then losslessly windowed;
            # otherwise one huge sentence could still overflow the model.
            sentences = [
                piece
                for sentence in sentences
                for piece in (
                    [sentence]
                    if estimate_tokens(sentence) <= token_budget
                    else [sentence[i:i + char_window] for i in range(0, len(sentence), char_window)]
                )
            ]
            nested: list[str] = []
            for sentence in sentences:
                candidate = "".join(nested) + sentence
                if nested and estimate_tokens(candidate) > token_budget:
                    chunks.append("".join(nested))
                    nested = []
                nested.append(sentence)
            if nested:
                chunks.append("".join(nested))
            continue
        candidate = "\n\n".join([*current, block])
        if current and estimate_tokens(candidate) > token_budget:
            flush()
        current.append(block)
    flush()
    return chunks


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = re.sub(r"\s+", "", item).casefold()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _merge_objects(parts: list[JDAnalysis], field: str, prefix: str, text_key: str) -> list[dict]:
    seen: set[str] = set()
    merged: list[dict] = []
    for part in parts:
        for item in getattr(part, field):
            payload = item.model_dump()
            key = re.sub(r"\s+", "", str(payload[text_key])).casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            payload["id"] = f"{prefix}_{len(merged) + 1:02d}"
            merged.append(payload)
    return merged


def merge_jd_analyses(parts: list[JDAnalysis]) -> JDAnalysis:
    if not parts:
        raise ValueError("No structured JD chunks to merge")

    def first(field: str):
        values = [getattr(part, field) for part in parts]
        return next((value for value in values if value not in (None, "", "unknown")), values[0])

    availability = [part.availability_requirements for part in parts]
    durations = [item.internship_duration_months for item in availability if item.internship_duration_months]
    days = [item.days_per_week for item in availability if item.days_per_week]
    payload = {
        "job_title": first("job_title"), "company": first("company"),
        "employment_type": first("employment_type"), "department": first("department"),
        "location": first("location"), "work_mode": first("work_mode"),
        "responsibilities": _merge_objects(parts, "responsibilities", "RESP", "content"),
        "core_requirements": _merge_objects(parts, "core_requirements", "REQ", "requirement"),
        "preferred_requirements": _merge_objects(parts, "preferred_requirements", "PREF", "requirement"),
        "hard_constraints": _merge_objects(parts, "hard_constraints", "HARD", "requirement"),
        "skills": _unique([value for part in parts for value in part.skills]),
        "domain_context": _unique([value for part in parts for value in part.domain_context]),
        "keywords": _unique([value for part in parts for value in part.keywords]),
        "availability_requirements": {
            "earliest_start_time": next((item.earliest_start_time for item in availability if item.earliest_start_time), None),
            "internship_duration_months": max(durations) if durations else None,
            "days_per_week": max(days) if days else None,
            "notes": _unique([value for item in availability for value in item.notes]),
        },
        "ambiguities": [item.model_dump() for part in parts for item in part.ambiguities],
    }
    return JDAnalysis.model_validate(payload)
