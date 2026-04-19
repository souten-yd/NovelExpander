from __future__ import annotations

import json


def label_units_with_llm(units: list[dict], characters: list[dict], max_retries: int = 2) -> list[dict]:
    """Placeholder LLM labeler with deterministic fallback.

    This implementation keeps a retry/JSON-validation shape so a real LLM can be
    wired in later without changing callers.
    """

    known = {c["canonical"] for c in characters}
    labeled: list[dict] = []

    for unit in units:
        payload = {
            "unit_id": unit.get("unit_id"),
            "speaker": "narrator" if unit.get("pass1_label") == "narration" else "unknown",
            "confidence": 0.25,
        }

        parsed = None
        for _ in range(max_retries + 1):
            try:
                raw = json.dumps(payload, ensure_ascii=False)
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
