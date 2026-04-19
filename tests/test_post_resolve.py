from __future__ import annotations

import pytest

from speaker_split.post_resolve import resolve_consistency


def _unit(speaker: str, confidence: float, *, pass1_label: str = "dialogue", prev_context: str = "") -> dict:
    return {
        "speaker": speaker,
        "confidence": confidence,
        "pass1_label": pass1_label,
        "prev_context": prev_context,
        "evidence": "llm",
    }


def test_confidence_threshold_drops_to_unknown():
    units = [_unit("alice", 0.2)]
    out = resolve_consistency(units, confidence_threshold=0.5)
    assert out[0]["speaker"] == "unknown"
    assert any(a["rule"] == "below_threshold_to_unknown" for a in out[0]["post_resolve_actions"])


def test_narration_is_forced_to_narrator():
    units = [_unit("alice", 0.1, pass1_label="narration")]
    out = resolve_consistency(units, confidence_threshold=0.9)
    assert out[0]["speaker"] == "narrator"


def test_two_party_pattern_completion_and_evidence():
    units = [
        _unit("alice", 0.9),
        _unit("bob", 0.9),
        _unit("alice", 0.9),
        _unit("unknown", 0.1),
        _unit("bob", 0.9),
    ]

    out = resolve_consistency(units, confidence_threshold=0.0)
    assert out[3]["speaker"] == "alice"
    assert out[3]["confidence"] <= 0.35
    assert "two_party_pattern" in out[3]["evidence"]
    assert any(a["rule"] == "two_party_unknown_completion" for a in out[3]["post_resolve_actions"])


def test_two_party_pattern_can_use_prev_narration_speech_verb_boost():
    units = [
        _unit("太郎", 0.9),
        _unit("花子", 0.9),
        _unit("太郎", 0.9),
        _unit("unknown", 0.2, prev_context="太郎は言った。"),
        _unit("花子", 0.9),
    ]

    out = resolve_consistency(units, confidence_threshold=0.0)
    assert out[3]["speaker"] == "太郎"
    assert out[3]["confidence"] == pytest.approx(0.3)
    assert "prev_narration_speech_verb" in out[3]["evidence"]


def test_non_matching_pattern_is_not_completed():
    units = [
        _unit("alice", 0.9),
        _unit("bob", 0.9),
        _unit("charlie", 0.9),
        _unit("unknown", 0.1),
        _unit("bob", 0.9),
    ]

    out = resolve_consistency(units, confidence_threshold=0.0)
    assert out[3]["speaker"] == "unknown"
