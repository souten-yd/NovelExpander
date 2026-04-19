from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from speaker_split.run import run_pipeline


@dataclass
class _RawBlock:
    html: str
    tag: str
    is_meta: bool
    doc_id: str
    order: int


def test_run_pipeline_writes_extended_report_and_characters_schema(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "speaker_split.run.extract_raw_blocks",
        lambda _epub: [
            _RawBlock("<p>「こんにちは」</p>", "p", False, "chapter1.xhtml", 0),
            _RawBlock("<p>地の文</p>", "p", False, "chapter1.xhtml", 1),
        ],
    )

    monkeypatch.setattr(
        "speaker_split.run.label_units_with_llm",
        lambda units, _chars, **_kwargs: [dict(u, speaker="unknown") for u in units],
    )
    monkeypatch.setattr("speaker_split.run.resolve_consistency", lambda units, **_kwargs: units)

    out_dir = tmp_path / "out"
    run_pipeline("my_book.epub", out_dir)

    report = json.loads((out_dir / "run_report.json").read_text(encoding="utf-8"))
    assert report["book_id"] == "my_book"
    assert report["total_blocks"] == 2
    assert report["total_scenes"] == 1
    assert report["total_units"] == 2
    assert report["dialogue_units"] == 1
    assert report["unknown_speakers"] == 2
    assert set(report["llm_errors"].keys()) == {"timeout", "rate_limit", "invalid_json", "other"}

    characters_payload = json.loads((out_dir / "characters.json").read_text(encoding="utf-8"))
    assert "characters" in characters_payload
    assert isinstance(characters_payload["characters"], list)
    assert all(set(c.keys()) == {"id", "display_name", "aliases"} for c in characters_payload["characters"])

    pass1_row = json.loads((out_dir / "units_pass1.jsonl").read_text(encoding="utf-8").splitlines()[0])
    final_row = json.loads((out_dir / "units_final.jsonl").read_text(encoding="utf-8").splitlines()[0])
    common = {"scene_id", "unit_id", "surface_text", "source_file", "source_indexes", "raw_html"}
    assert common.issubset(pass1_row.keys())
    assert common.issubset(final_row.keys())


def test_run_pipeline_raises_when_lineage_fields_are_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "speaker_split.run.extract_raw_blocks",
        lambda _epub: [_RawBlock("<p>本文</p>", "p", False, "chapter1.xhtml", 0)],
    )
    monkeypatch.setattr(
        "speaker_split.run.segment_scene_units",
        lambda _scene: [
            {
                "scene_id": "scene_0001",
                "unit_id": "scene_0001_u0000",
                "surface_text": "本文",
                "normalized_text": "本文",
                "unit_type": "narration",
                "pass1_label": "narration",
                "mode": "narrative",
                "speaker": "narrator",
                "speaker_canonical_id": "narrator",
                "speaker_candidates": [],
                "confidence": 1.0,
                "evidence": "test",
                "alternatives": [],
                "post_resolve_actions": [],
                "source_indexes": [0],
                "chapter_title": "",
                "order_in_scene": 0,
                "prev_context": "",
                "next_context": "",
            }
        ],
    )
    monkeypatch.setattr("speaker_split.run.label_units_with_llm", lambda units, _chars, **_kwargs: units)
    monkeypatch.setattr("speaker_split.run.resolve_consistency", lambda units, **_kwargs: units)

    with pytest.raises(ValueError, match="lineage validation failed"):
        run_pipeline("my_book.epub", tmp_path / "out")
