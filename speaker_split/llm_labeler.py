from __future__ import annotations

import json
from typing import Callable


def _default_llm_response(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def label_units_with_llm(
    units: list[dict],
    characters: list[dict],
    max_retries: int = 3,
    llm_call: Callable[[dict], str] | None = None,
    model: str | None = None,
    context_prev: int = 1,
    context_next: int = 1,
) -> list[dict]:
    """LLM labeler with JSON validation and unknown fallback."""

    known = {c["canonical"] for c in characters}
    labeled: list[dict] = []
    caller = llm_call or _default_llm_response

    for unit in units:
        payload = {
            "model": model,
            "context_prev": context_prev,
            "context_next": context_next,
            "unit_id": unit.get("unit_id"),
            "speaker": "narrator" if unit.get("pass1_label") == "narration" else "unknown",
            "confidence": 0.25,
        }

        parsed = None
        for _ in range(max_retries):
            try:
                raw = caller(payload)
                candidate = json.loads(raw)
                if not isinstance(candidate, dict) or "speaker" not in candidate:
                    raise ValueError("invalid json payload")
                parsed = candidate
                break
            except Exception:
                continue

        if parsed is None:
            parsed = {"speaker": "unknown", "confidence": 0.0}

        speaker = parsed.get("speaker", "unknown")
        if speaker not in known:
            speaker = "unknown"

        out = dict(unit)
        out["speaker"] = speaker
        out["confidence"] = float(parsed.get("confidence", 0.0))
        labeled.append(out)

    return labeled
