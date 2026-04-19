import json
from pathlib import Path

from speaker_split.scene_splitter import split_scenes
from speaker_split.unit_segmenter import segment_scene_units


FIXTURE = Path(__file__).parent / "fixtures" / "sample_blocks.json"


def test_golden_counts_and_source_fields_are_preserved():
    blocks = json.loads(FIXTURE.read_text(encoding="utf-8"))

    before_surface = [b["surface_text"] for b in blocks]
    before_raw = [b["raw_html"] for b in blocks]
    before_sources = [(b["source_file"], tuple(b["source_indexes"])) for b in blocks]

    scenes = split_scenes(blocks)
    units = []
    for s in scenes:
        units.extend(segment_scene_units({"scene_id": s.scene_id, "blocks": s.blocks}))

    assert len(blocks) == 4
    assert len(scenes) == 2
    assert len(units) == 5

    # Freeze a subset of speaker defaults from pass1(units_final互換の最小形) and ensure
    # unknownを含んでもパイプライン形状検証は完走できる。
    assert units[0]["speaker"] == "narrator"
    assert units[3]["speaker"] == "unknown"
    assert any(u["speaker"] == "unknown" for u in units)

    flattened = [b for s in scenes for b in s.blocks]
    assert [b["surface_text"] for b in flattened] == before_surface
    assert [b["raw_html"] for b in flattened] == before_raw
    assert [(b["source_file"], tuple(b["source_indexes"])) for b in flattened] == before_sources
