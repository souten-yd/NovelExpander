from __future__ import annotations

import re

_SPEECH_VERB_RE = re.compile(r"(?P<subject>[^\s、。『「』」]{1,20})は[^。\n]*?(?:言った|言う|話した|叫んだ|呟いた|つぶやいた|尋ねた|答えた)")


def _append_action(unit: dict, *, rule: str, before_speaker: str, after_speaker: str, before_confidence: float, after_confidence: float, reason: str) -> None:
    actions = unit.setdefault("post_resolve_actions", [])
    actions.append(
        {
            "rule": rule,
            "before_speaker": before_speaker,
            "after_speaker": after_speaker,
            "before_confidence": before_confidence,
            "after_confidence": after_confidence,
            "reason": reason,
        }
    )


def _append_evidence(unit: dict, reason: str) -> None:
    evidence = str(unit.get("evidence") or "")
    if evidence:
        unit["evidence"] = f"{evidence}|{reason}"
    else:
        unit["evidence"] = reason


def _extract_subject_from_prev_narration(unit: dict) -> str | None:
    prev_text = str(unit.get("prev_context") or "")
    if not prev_text:
        return None

    match = _SPEECH_VERB_RE.search(prev_text)
    if not match:
        return None
    subject = match.group("subject").strip("「『」』（）()")
    return subject or None


def _suppressed_confidence(base_confidence: float, *, boost: bool = False) -> float:
    capped = min(max(base_confidence, 0.0), 0.35)
    if boost:
        return min(capped + 0.1, 0.45)
    return capped


def resolve_consistency(units: list[dict], confidence_threshold: float = 0.5) -> list[dict]:
    """Second-pass consistency fix.

    Rule 1: narration units are narrator.
    Rule 2: empty/invalid speaker becomes unknown.
    Rule 3: confidence below threshold is dropped to unknown (except narration).
    Rule 4: if pattern A/B/A/unknown/B is detected, fill unknown with A only.
    Rule 5: leave per-unit post_resolve_actions for before/after debugging.
    """

    resolved: list[dict] = []
    for unit in units:
        u = dict(unit)
        u["post_resolve_actions"] = []

        before_speaker = str(u.get("speaker") or "")
        before_conf = float(u.get("confidence", 0.0))

        if u.get("pass1_label") == "narration":
            u["speaker"] = "narrator"
            _append_action(
                u,
                rule="narration_to_narrator",
                before_speaker=before_speaker,
                after_speaker="narrator",
                before_confidence=before_conf,
                after_confidence=before_conf,
                reason="pass1_label is narration",
            )
            before_speaker = "narrator"

        if not u.get("speaker"):
            u["speaker"] = "unknown"
            _append_action(
                u,
                rule="empty_to_unknown",
                before_speaker=before_speaker,
                after_speaker="unknown",
                before_confidence=before_conf,
                after_confidence=before_conf,
                reason="speaker is empty",
            )
            before_speaker = "unknown"

        confidence = float(u.get("confidence", 0.0))
        if confidence < confidence_threshold and u.get("pass1_label") != "narration":
            after_speaker = "unknown"
            if str(u.get("speaker") or "") != "unknown":
                _append_action(
                    u,
                    rule="below_threshold_to_unknown",
                    before_speaker=str(u.get("speaker") or ""),
                    after_speaker=after_speaker,
                    before_confidence=confidence,
                    after_confidence=confidence,
                    reason=f"confidence {confidence:.3f} < threshold {confidence_threshold:.3f}",
                )
            u["speaker"] = after_speaker

        resolved.append(u)

    for i in range(3, len(resolved) - 1):
        cur = resolved[i]
        if str(cur.get("speaker") or "") != "unknown":
            continue

        s0 = str(resolved[i - 3].get("speaker") or "")
        s1 = str(resolved[i - 2].get("speaker") or "")
        s2 = str(resolved[i - 1].get("speaker") or "")
        s4 = str(resolved[i + 1].get("speaker") or "")
        if not (s0 and s1 and s2 and s4):
            continue
        if s0 in {"unknown", "narrator"} or s1 in {"unknown", "narrator"}:
            continue
        if not (s0 == s2 and s1 == s4 and s0 != s1):
            continue

        reason = "two_party_pattern A/B/A/unknown/B"
        subject = _extract_subject_from_prev_narration(cur)
        boosted = bool(subject and subject == s0)
        if boosted:
            reason += f" + prev_narration_speech_verb({subject})"

        before_conf = float(cur.get("confidence", 0.0))
        after_conf = _suppressed_confidence(before_conf, boost=boosted)
        cur["speaker"] = s0
        cur["confidence"] = after_conf
        _append_evidence(cur, f"post_resolve:{reason}")
        _append_action(
            cur,
            rule="two_party_unknown_completion",
            before_speaker="unknown",
            after_speaker=s0,
            before_confidence=before_conf,
            after_confidence=after_conf,
            reason=reason,
        )

    return resolved
