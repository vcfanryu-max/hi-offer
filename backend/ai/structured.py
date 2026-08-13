from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from backend.ai.llm_client import OpenAICompatibleClient
from backend.ai.prompts.loader import load_prompt
from backend.config import STRUCTURED_REPAIR_PROMPT_VERSION
from backend.errors import StructuredOutputError


T = TypeVar("T", bound=BaseModel)
Normalizer = Callable[[dict[str, Any]], dict[str, Any]]
SemanticValidator = Callable[[T], list[dict[str, Any]]]
SENSITIVE_KEY = re.compile(
    r"^(?:api[_-]?key|authorization|credential|secret|access[_-]?token|refresh[_-]?token|bearer[_-]?token)$",
    re.IGNORECASE,
)
BEARER_VALUE = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+")
SENSITIVE_JSON_VALUE = re.compile(
    r'(?i)(["\']?(?:api[_-]?key|authorization|credential|secret|token)["\']?\s*[:=]\s*["\'])(.*?)(["\'])'
)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if SENSITIVE_KEY.search(str(key)) else _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        value = BEARER_VALUE.sub("Bearer [REDACTED]", value)
        return SENSITIVE_JSON_VALUE.sub(r"\1[REDACTED]\3", value)
    return value


@dataclass
class StructuredTrace:
    module: str
    prompt_version: str
    provider: str
    model: str
    request_id: str
    raw_output: str = ""
    parsed_json: dict[str, Any] | None = None
    normalized_json: dict[str, Any] | None = None
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    repair_attempted: bool = False
    repair_prompt_version: str | None = None
    repair_request_id: str | None = None
    repair_raw_output: str | None = None
    repair_parsed_json: dict[str, Any] | None = None
    repair_normalized_json: dict[str, Any] | None = None
    repair_validation_errors: list[dict[str, Any]] = field(default_factory=list)
    validation_result: str = "pending"
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def public_dict(self, *, generation_id: int | None = None) -> dict[str, Any]:
        payload = _redact(asdict(self))
        payload["generation_id"] = generation_id
        return payload


@dataclass
class StructuredResult(Generic[T]):
    value: T
    trace: StructuredTrace


def parse_json_object(raw_output: str) -> dict[str, Any]:
    cleaned = raw_output.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def identity_normalizer(value: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(value)


def _enum(value: Any, equivalents: dict[str, str]) -> Any:
    if not isinstance(value, str):
        return value
    key = value.strip().casefold()
    return equivalents.get(key, value)


LEVELS = {"高": "high", "中": "medium", "低": "low", "高风险": "high", "中风险": "medium", "低风险": "low"}


def normalize_jd_analysis(value: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(value)
    normalized["employment_type"] = _enum(normalized.get("employment_type"), {
        "全职": "full_time", "实习": "internship", "兼职": "part_time", "合同": "contract", "未知": "unknown"
    })
    importance = {"必须": "must", "核心": "must", "优先": "should", "建议": "should", "加分": "nice_to_have"}
    for key in ("responsibilities", "core_requirements"):
        for item in normalized.get(key, []) if isinstance(normalized.get(key), list) else []:
            if isinstance(item, dict) and "importance" in item:
                item["importance"] = _enum(item["importance"], importance)
    availability = normalized.get("availability_requirements")
    if isinstance(availability, dict):
        for key in ("internship_duration_months", "days_per_week"):
            item = availability.get(key)
            if isinstance(item, str) and re.fullmatch(r"\s*\d+\s*", item):
                availability[key] = int(item.strip())
    return normalized


def normalize_match_analysis(value: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(value)
    score = normalized.get("match_score")
    if isinstance(score, str) and re.fullmatch(r"\s*\d{1,3}\s*%?\s*", score):
        normalized["match_score"] = int(score.strip().removesuffix("%").strip())
    normalized["fit_level"] = _enum(normalized.get("fit_level"), {
        "高度匹配": "strong_fit", "部分匹配": "partial_fit", "弱匹配": "weak_fit", "证据不足": "insufficient_evidence"
    })
    for item in normalized.get("strong_matches", []) if isinstance(normalized.get("strong_matches"), list) else []:
        if isinstance(item, dict):
            item["match_type"] = _enum(item.get("match_type"), {"直接匹配": "direct", "可迁移": "transferable"})
    for item in normalized.get("gaps", []) if isinstance(normalized.get("gaps"), list) else []:
        if isinstance(item, dict):
            item["severity"] = _enum(item.get("severity"), LEVELS)
    return normalized


def normalize_hr_message(value: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(value)
    normalized["status"] = _enum(normalized.get("status"), {"可生成": "ready", "需要补充": "needs_input"})
    return normalized


def normalize_resume_advice(value: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(value)
    normalized["fit_level"] = _enum(normalized.get("fit_level"), {
        "高度匹配": "strong_fit", "部分匹配": "partial_fit", "弱匹配": "weak_fit", "证据不足": "insufficient_evidence"
    })
    normalized["advice_mode"] = _enum(normalized.get("advice_mode"), {
        "润色": "polish", "桥接": "bridge", "重定位": "reposition", "需要补充": "needs_input"
    })
    actions = {"重写": "rewrite", "排序": "reorder", "删除": "remove", "澄清": "clarify", "如属实则补充": "add_if_true"}
    for item in normalized.get("suggestions", []) if isinstance(normalized.get("suggestions"), list) else []:
        if isinstance(item, dict):
            item["priority"] = _enum(item.get("priority"), LEVELS)
            item["action_type"] = _enum(item.get("action_type"), actions)
    return normalized


NORMALIZERS: dict[str, Normalizer] = {
    "resume_structure": identity_normalizer,
    "jd_analysis": normalize_jd_analysis,
    "match_analysis": normalize_match_analysis,
    "hr_message": normalize_hr_message,
    "resume_advice": normalize_resume_advice,
}


def _format_errors(exc: ValidationError) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for item in exc.errors(include_url=False):
        location = ".".join(str(part) for part in item.get("loc", ())) or "$"
        error_type = item.get("type", "validation_error")
        expected = {
            "missing": "required field", "int_type": "integer", "int_parsing": "integer",
            "less_than_equal": f"value <= {item.get('ctx', {}).get('le')}",
            "greater_than_equal": f"value >= {item.get('ctx', {}).get('ge')}",
            "literal_error": item.get("ctx", {}).get("expected", "allowed enum value"),
            "extra_forbidden": "no extra field", "string_too_short": "non-empty string",
            "string_too_long": f"string <= {item.get('ctx', {}).get('max_length')} chars",
            "too_long": "array within maxItems", "value_error": "model invariant",
        }.get(error_type, error_type)
        errors.append({
            "error_code": error_type, "field_path": location, "expected": expected,
            "received": "<missing>" if error_type == "missing" else _redact(item.get("input")),
            "validation_message": item.get("msg", "Validation failed"),
        })
    return errors


def _parse_error(message: str) -> list[dict[str, Any]]:
    return [{"error_code": "json_parse_error", "field_path": "$", "expected": "valid JSON object", "received": "unparseable raw output", "validation_message": message}]


def build_output_contract(schema: type[BaseModel]) -> str:
    return "\n\n".join([
        "## Runtime Structured Output Contract",
        "以下 JSON Schema 由当前 Pydantic Model.model_json_schema() 实时生成，是字段名、类型、required、enum 与长度约束的唯一技术依据。",
        json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2),
        "字段名必须使用 Schema 中的英文 canonical names；JSON value 可以使用中文。只返回一个 JSON object，不得返回 Markdown、代码围栏或 JSON 外说明。",
    ])


def _repair_task(*, raw_output: str, parsed_json: dict[str, Any] | None, normalized_json: dict[str, Any] | None,
                 validation_errors: list[dict[str, Any]], schema: type[BaseModel], repair_context: str) -> str:
    return "\n\n".join([
        "EXPECTED_SCHEMA:\n" + json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2),
        "VALIDATION_ERRORS:\n" + json.dumps(validation_errors, ensure_ascii=False, indent=2),
        "APPLICATION_POLICY_CONTEXT:\n" + repair_context,
        "ORIGINAL_OUTPUT:\n" + raw_output,
        "PARSED_JSON:\n" + json.dumps(parsed_json, ensure_ascii=False, indent=2),
        "NORMALIZED_JSON:\n" + json.dumps(normalized_json, ensure_ascii=False, indent=2),
    ])


def _parse_normalize_validate(raw_output: str, schema: type[T], normalizer: Normalizer,
                              semantic_validator: SemanticValidator | None = None) -> tuple[dict[str, Any] | None, dict[str, Any] | None, T | None, list[dict[str, Any]]]:
    try:
        parsed = parse_json_object(raw_output)
    except ValueError as exc:
        return None, None, None, _parse_error(str(exc))
    normalized = normalizer(parsed)
    try:
        value = schema.model_validate(normalized)
    except ValidationError as exc:
        return parsed, normalized, None, _format_errors(exc)
    semantic_errors = semantic_validator(value) if semantic_validator else []
    if semantic_errors:
        return parsed, normalized, None, semantic_errors
    return parsed, normalized, value, []


async def generate_structured(*, client: OpenAICompatibleClient, module: str, prompt_version: str,
                              system_prompt: str, task_prompt: str, schema: type[T],
                              normalizer: Normalizer | None = None, semantic_validator: SemanticValidator | None = None,
                              repair_context: str = "", diagnostics: dict[str, Any] | None = None,
                              temperature: float = 0.2) -> StructuredResult[T]:
    normalize = normalizer or NORMALIZERS.get(module, identity_normalizer)
    trace = StructuredTrace(module=module, prompt_version=prompt_version, provider=client.settings.provider,
                            model=client.settings.model, request_id=str(uuid4()), diagnostics=diagnostics or {})
    trace.raw_output = await client.complete_text(
        system_prompt=system_prompt, user_prompt=f"{task_prompt}\n\n{build_output_contract(schema)}",
        schema_name=f"{module}_{prompt_version}", temperature=temperature,
    )
    parsed, normalized, value, errors = _parse_normalize_validate(trace.raw_output, schema, normalize, semantic_validator)
    trace.parsed_json, trace.normalized_json, trace.validation_errors = parsed, normalized, errors
    if value is not None:
        trace.validation_result = "valid"
        return StructuredResult(value=value, trace=trace)

    trace.repair_attempted = True
    trace.repair_prompt_version = STRUCTURED_REPAIR_PROMPT_VERSION
    trace.repair_request_id = str(uuid4())
    trace.repair_raw_output = await client.complete_text(
        system_prompt=load_prompt("structured_repair", STRUCTURED_REPAIR_PROMPT_VERSION),
        user_prompt=_repair_task(raw_output=trace.raw_output, parsed_json=parsed, normalized_json=normalized,
                                 validation_errors=errors, schema=schema, repair_context=repair_context),
        schema_name=f"structured_repair_{STRUCTURED_REPAIR_PROMPT_VERSION}", temperature=0,
    )
    repaired_parsed, repaired_normalized, repaired_value, repaired_errors = _parse_normalize_validate(
        trace.repair_raw_output, schema, normalize, semantic_validator
    )
    trace.repair_parsed_json, trace.repair_normalized_json = repaired_parsed, repaired_normalized
    trace.repair_validation_errors = repaired_errors
    if repaired_value is not None:
        trace.validation_result = "repaired_valid"
        return StructuredResult(value=repaired_value, trace=trace)

    trace.validation_result = "invalid_after_repair"
    raise StructuredOutputError(f"{module} 的模型输出在一次自动结构修复后仍未通过校验。", trace=trace)
