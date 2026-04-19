from __future__ import annotations

import json
from pathlib import Path

from speaker_split.debug_view import build_debug_html, write_debug_html
from speaker_split.run import run_pipeline


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def test_build_debug_html_contains_required_columns_and_filters(tmp_path: Path):
    units_path = tmp_path / "units_final.jsonl"
    scenes_path = tmp_path / "scenes.jsonl"

    _write_jsonl(
        units_path,
        [
            {
                "scene_id": "scene_0001",
                "text": "「こんにちは」",
                "pass1_label": "dialogue",
                "speaker": "unknown",
                "confidence": 0.2,
            }
        ],
    )
    _write_jsonl(
        scenes_path,
        [
            {
                "scene_id": "scene_0001",
                "blocks": [
                    {
                        "chapter_title": "第1章",
                        "text": "前文",
                        "source_file": "chapter1.xhtml",
                        "source_indexes": [1],
                    },
                    {
                        "text": "後文",
                        "source_file": "chapter1.xhtml",
                        "source_indexes": [2],
                    },
                ],
            }
        ],
    )

    html = build_debug_html(units_path, scenes_path)

    assert "chapter_title" in html
    assert "normalized_text" in html
    assert "unit_type" in html
    assert "unknownのみ" in html
    assert "confidence昇順" in html
    assert "const ROWS" in html


def test_run_pipeline_exports_debug_html_only_when_option_enabled(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("speaker_split.run.extract_raw_blocks", lambda _epub: [])
    monkeypatch.setattr("speaker_split.run.split_scenes", lambda _blocks, **_kwargs: [])
    monkeypatch.setattr("speaker_split.run.build_characters", lambda _units: [])
    monkeypatch.setattr("speaker_split.run.label_units_with_llm", lambda units, _chars, **_kwargs: units)
    monkeypatch.setattr("speaker_split.run.resolve_consistency", lambda units, **_kwargs: units)

    out_a = tmp_path / "without"
    out_b = tmp_path / "with"

    run_pipeline("dummy.epub", out_a, export_debug_html=False)
    assert not (out_a / "debug_view.html").exists()

    run_pipeline("dummy.epub", out_b, export_debug_html=True)
    assert (out_b / "debug_view.html").exists()


def test_write_debug_html_writes_file(tmp_path: Path):
    units_path = tmp_path / "units_final.jsonl"
    scenes_path = tmp_path / "scenes.jsonl"
    out_path = tmp_path / "debug_view.html"

    _write_jsonl(units_path, [])
    _write_jsonl(scenes_path, [])

    result = write_debug_html(units_path, scenes_path, out_path)
    assert result == out_path
    assert out_path.exists()
