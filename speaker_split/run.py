from __future__ import annotations

import argparse
from pathlib import Path

from .candidate_builder import build_characters
from .epub_ingest import extract_raw_blocks
from .html_normalize import extract_text_fields
from .io_utils import ensure_dir, write_json, write_jsonl
from .llm_labeler import label_units_with_llm
from .post_resolve import resolve_consistency
from .scene_splitter import split_scenes
from .unit_segmenter import segment_scene_units


def run_pipeline(epub_path: str | Path, output_dir: str | Path) -> dict:
    out_dir = ensure_dir(output_dir)

    raw_blocks = extract_raw_blocks(epub_path)
    normalized_blocks: list[dict] = []
    for rb in raw_blocks:
        extracted = extract_text_fields(rb.html)
        text = extracted["text"]
        if not text:
            continue
        normalized_blocks.append(
            {
                "doc_id": rb.doc_id,
                "order": rb.order,
                "text": text,
                "surface_text": text,
                "text_with_ruby": extracted["text_with_ruby"],
                "ruby_map": extracted["ruby_map"],
                "raw_html": rb.html,
                "source_file": rb.doc_id,
                "source_indexes": [rb.order],
                "tag": rb.tag,
                "is_meta": rb.is_meta,
            }
        )
    write_jsonl(out_dir / "normalized_blocks.jsonl", normalized_blocks)

    scenes_obj = split_scenes(normalized_blocks)
    scenes = [{"scene_id": s.scene_id, "blocks": s.blocks} for s in scenes_obj]
    write_jsonl(out_dir / "scenes.jsonl", scenes)

    units_pass1: list[dict] = []
    units_final: list[dict] = []
    error_count = 0
    error_scenes: list[dict] = []

    for scene in scenes:
        try:
            pass1_units = segment_scene_units(scene)
            units_pass1.extend(pass1_units)

            characters = build_characters(pass1_units)
            llm_units = label_units_with_llm(pass1_units, characters)
            resolved = resolve_consistency(llm_units)
            units_final.extend(resolved)
        except Exception as exc:  # continue on scene error
            error_count += 1
            error_scenes.append(
                {
                    "scene_id": scene.get("scene_id"),
                    "error": str(exc),
                }
            )

    write_jsonl(out_dir / "units_pass1.jsonl", units_pass1)
    write_jsonl(out_dir / "units_final.jsonl", units_final)

    characters = build_characters(units_pass1)
    write_json(out_dir / "characters.json", characters)

    report = {
        "epub_path": str(epub_path),
        "normalized_blocks": len(normalized_blocks),
        "scenes": len(scenes),
        "units_pass1": len(units_pass1),
        "units_final": len(units_final),
        "scene_errors": error_count,
        "error_scenes": error_scenes,
    }
    write_json(out_dir / "run_report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Speaker split pipeline")
    parser.add_argument("epub_path", help="Input EPUB path")
    parser.add_argument("-o", "--output-dir", default="speaker_split_out", help="Output directory")
    args = parser.parse_args()

    report = run_pipeline(args.epub_path, args.output_dir)
    print(
        f"done scenes={report['scenes']} units_final={report['units_final']} errors={report['scene_errors']}"
    )


if __name__ == "__main__":
    main()
