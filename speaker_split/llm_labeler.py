from __future__ import annotations

import json
from typing import Any, Callable, Protocol


class LLMClient(Protocol):
    """OpenAI-compatible LLM client interface."""

    def call(
        self,
        *,
        model: str | None,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> str: ...


class OpenAICompatibleCallableClient:
    """Adapter for callable-based OpenAI-compatible invocation."""

    def __init__(self, caller: Callable[[dict], str]) -> None:
        self._caller = caller

    def call(
        self,
        *,
        model: str | None,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "response_format": response_format,
            "timeout": timeout,
        }
        return self._caller(payload)


def _default_llm_response(payload: dict) -> str:
    if payload.get("response_format"):
        return json.dumps(
            {
                "speaker": "unknown",
                "speaker_canonical_id": "unknown",
                "confidence": 0.0,
                "evidence": "no_llm_configured",
                "alternatives": [],
                "unit_type": "unknown",
                "mode": "unknown",
            },
            ensure_ascii=False,
        )
    return json.dumps(payload, ensure_ascii=False)


DEFAULT_RULES = [
    "Return JSON object only.",
    "speaker must be one of candidate_speakers or unknown.",
    "confidence must be float in [0.0, 1.0].",
]


def _normalize_error_type(exc: Exception) -> str:
    name = exc.__class__.__name__.lower()
    text = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in name or "timed out" in text:
        return "timeout"
    if "rate" in text and "limit" in text:
        return "rate_limit"
    if isinstance(exc, json.JSONDecodeError) or "json" in name:
        return "invalid_json"
    return "other"


def _build_unit_input(
    units: list[dict],
    index: int,
    candidate_speakers: list[str],
    *,
    context_prev: int,
    context_next: int,
) -> dict[str, Any]:
    unit = units[index]
    start = max(0, index - context_prev)
    end = min(len(units), index + context_next + 1)
    prev_units = [u.get("surface_text", "") for u in units[start:index]]
    next_units = [u.get("surface_text", "") for u in units[index + 1 : end]]
    return {
        "chapter_title": unit.get("chapter_title"),
        "scene_id": unit.get("scene_id"),
        "candidate_speakers": candidate_speakers,
        "previous_units": prev_units,
        "target_unit": unit.get("surface_text"),
        "next_units": next_units,
        "rules": DEFAULT_RULES,
    }


def _build_messages(unit_input: dict[str, Any], strict_json: bool) -> list[dict[str, str]]:
    system = "You are a speaker attribution assistant."
    if strict_json:
        system += " STRICT: return only valid JSON with required keys."
    user = json.dumps(unit_input, ensure_ascii=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def label_units_with_llm(
    units: list[dict],
    characters: list[dict],
    max_retries: int = 3,
    llm_call: Callable[[dict], str] | None = None,
    model: str | None = None,
    context_prev: int = 1,
    context_next: int = 1,
    llm_client: LLMClient | None = None,
    timeout_sec: float | None = None,
    run_report: dict | None = None,
) -> list[dict]:
    """LLM labeler with JSON validation and unknown fallback."""

    known = {c["id"] for c in characters}
    labeled: list[dict] = []
    client: LLMClient = llm_client or OpenAICompatibleCallableClient(llm_call or _default_llm_response)
    candidate_speakers = [c["id"] for c in characters]
    errors = {"timeout": 0, "rate_limit": 0, "invalid_json": 0, "other": 0}

    for idx, unit in enumerate(units):
        unit_input = _build_unit_input(
            units,
            idx,
            candidate_speakers,
            context_prev=context_prev,
            context_next=context_next,
        )

        parsed = None
        # retry strategy:
        # 1st fail -> retry same prompt
        # 2nd fail -> strict JSON prompt
        # 3rd fail -> fallback unknown
        for attempt in range(max_retries):
            strict_json = attempt >= 2
            try:
                raw = client.call(
                    model=model,
                    messages=_build_messages(unit_input, strict_json),
                    response_format={"type": "json_object"} if strict_json else None,
                    timeout=timeout_sec,
                )
                candidate = json.loads(raw)
                if not isinstance(candidate, dict) or "speaker" not in candidate:
                    raise ValueError("invalid_json")
                parsed = candidate
                break
            except Exception as exc:
                err_type = _normalize_error_type(exc)
                errors[err_type] = errors.get(err_type, 0) + 1
                continue

        if parsed is None:
            parsed = {
                "speaker": "unknown",
                "speaker_canonical_id": "unknown",
                "confidence": 0.0,
                "evidence": "llm_fallback_after_retries",
                "alternatives": [],
                "unit_type": unit.get("unit_type", "unknown"),
                "mode": unit.get("mode", "unknown"),
            }

        speaker = parsed.get("speaker", "unknown")
        if speaker not in known:
            speaker = "unknown"

        out = dict(unit)
        out["speaker"] = speaker
        out["speaker_canonical_id"] = str(parsed.get("speaker_canonical_id") or speaker)
        out["confidence"] = float(parsed.get("confidence", 0.0))
        out["evidence"] = parsed.get("evidence", "llm")
        out["alternatives"] = parsed.get("alternatives", [])
        out["unit_type"] = parsed.get("unit_type", out.get("unit_type"))
        out["mode"] = parsed.get("mode", out.get("mode"))
        labeled.append(out)

    if run_report is not None:
        report_errors = run_report.setdefault("llm_errors", {"timeout": 0, "rate_limit": 0, "invalid_json": 0, "other": 0})
        for k, v in errors.items():
            report_errors[k] = int(report_errors.get(k, 0)) + int(v)

    return labeled
