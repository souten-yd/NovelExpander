from __future__ import annotations


def resolve_consistency(units: list[dict], confidence_threshold: float = 0.0) -> list[dict]:
    """Second-pass consistency fix.

    Rule 1: narration units are narrator.
    Rule 2: empty/invalid speaker becomes unknown.
    """

    resolved: list[dict] = []
    for unit in units:
        u = dict(unit)
        if u.get("pass1_label") == "narration":
            u["speaker"] = "narrator"
        if not u.get("speaker"):
            u["speaker"] = "unknown"
        confidence = float(u.get("confidence", 0.0))
        if confidence < confidence_threshold and u.get("pass1_label") != "narration":
            u["speaker"] = "unknown"
        resolved.append(u)
    return resolved
