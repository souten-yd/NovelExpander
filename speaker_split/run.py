from __future__ import annotations

import argparse
import json
from pathlib import Path

from .candidate_builder import build_characters
from .epub_ingest import extract_raw_blocks
from .html_normalize import extract_text_fields
from .io_utils import ensure_dir, write_json, write_jsonl
from .llm_labeler import label_units_with_llm
from .post_resolve import resolve_consistency
from .scene_splitter import split_scenes
from .unit_segmenter import segment_scene_units
from .debug_view import write_debug_html


def _read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _scene_matches_chapter_filter(scene: dict, chapter_filter: str | None) -> bool:
    if not chapter_filter:
        return True
    needle = chapter_filter.strip().lower()
    if not needle:
        return True

    for block in scene.get("blocks", []):
        chapter_title = str(block.get("chapter_title") or "").lower()
        source_file = str(block.get("source_file") or "").lower()
        text = str(block.get("text") or "").lower()
        if needle in chapter_title or needle in source_file or needle in text:
            return True
    return False


def _resolve_block_type(tag: str, is_meta: bool) -> str:
    if is_meta:
        return "meta"
    low = tag.lower()
    if low in {"h1", "h2", "h3"}:
        return "heading"
    if low == "hr":
        return "scene_break"
    return "paragraph"


def run_pipeline(
    epub_path: str | Path,
    output_dir: str | Path,
    *,
    model: str = "gpt-4.1-mini",
    max_scene_blocks: int | None = None,
    context_prev: int = 1,
    context_next: int = 1,
    confidence_threshold: float = 0.5,
    resume: bool = False,
    chapter_filter: str | None = None,
    max_scenes: int | None = None,
    dry_run_no_llm: bool = False,
    export_debug_html: bool = False,
) -> dict:
    out_dir = ensure_dir(output_dir)

    normalized_path = out_dir / "normalized_blocks.jsonl"
    if resume and normalized_path.exists():
        normalized_blocks = _read_jsonl(normalized_path)
    else:
        raw_blocks = extract_raw_blocks(epub_path)
        book_id = Path(epub_path).stem
        current_chapter_title = ""
        normalized_blocks: list[dict] = []
        for idx, rb in enumerate(raw_blocks):
            extracted = extract_text_fields(rb.html)
            text = extracted["text"]
            if not text:
                continue
            block_type = _resolve_block_type(rb.tag, rb.is_meta)
            if block_type == "heading":
                current_chapter_title = text
            normalized_blocks.append(
                {
                    "book_id": book_id,
                    "index": idx,
                    "doc_id": rb.doc_id,
                    "order": rb.order,
                    "block_type": block_type,
                    "chapter_title": current_chapter_title,
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
        write_jsonl(normalized_path, normalized_blocks)

    scenes_path = out_dir / "scenes.jsonl"
    if resume and scenes_path.exists():
        scenes = _read_jsonl(scenes_path)
    else:
        scenes_obj = split_scenes(normalized_blocks, max_scene_blocks=max_scene_blocks)
        scenes = [{"scene_id": s.scene_id, "blocks": s.blocks} for s in scenes_obj]
        write_jsonl(scenes_path, scenes)

    target_scenes = [s for s in scenes if _scene_matches_chapter_filter(s, chapter_filter)]
    if max_scenes is not None:
        target_scenes = target_scenes[:max_scenes]

    units_pass1: list[dict] = []
    units_final: list[dict] = []
    error_count = 0
    error_scenes: list[dict] = []

    for scene in target_scenes:
        try:
            pass1_units = segment_scene_units(scene)
            units_pass1.extend(pass1_units)

            if dry_run_no_llm:
                units_final.extend(pass1_units)
                continue

            characters = build_characters(pass1_units)
            llm_units = label_units_with_llm(
                pass1_units,
                characters,
                model=model,
                context_prev=context_prev,
                context_next=context_next,
            )
            resolved = resolve_consistency(llm_units, confidence_threshold=confidence_threshold)
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
        "model": model,
        "normalized_blocks": len(normalized_blocks),
        "scenes": len(scenes),
        "target_scenes": len(target_scenes),
        "units_pass1": len(units_pass1),
        "units_final": len(units_final),
        "scene_errors": error_count,
        "error_scenes": error_scenes,
        "dry_run_no_llm": dry_run_no_llm,
        "resume": resume,
    }

    if export_debug_html:
        write_debug_html(
            out_dir / "units_final.jsonl",
            out_dir / "scenes.jsonl",
            out_dir / "debug_view.html",
        )

    write_json(out_dir / "run_report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Speaker split pipeline")
    parser.add_argument("epub_path", help="Input EPUB path")
    parser.add_argument("-o", "--output-dir", default="speaker_split_out", help="Output directory")
    parser.add_argument("--model", default="gpt-4.1-mini", help="LLM model name")
    parser.add_argument("--max-scene-blocks", type=int, default=None, help="Maximum blocks per scene")
    parser.add_argument("--context-prev", type=int, default=1, help="Previous units to include in LLM context")
    parser.add_argument("--context-next", type=int, default=1, help="Next units to include in LLM context")
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        help="Confidence threshold below which speaker is replaced with unknown",
    )
    parser.add_argument("--resume", action="store_true", help="Reuse existing intermediate outputs when present")
    parser.add_argument(
        "--chapter-filter",
        default=None,
        help="Only process scenes whose chapter title/source/text contains this substring",
    )
    parser.add_argument("--max-scenes", type=int, default=None, help="Maximum number of scenes to process")
    parser.add_argument(
        "--dry-run-no-llm",
        action="store_true",
        help="Skip LLM labeling and copy pass1 units directly to units_final.jsonl",
    )
    parser.add_argument(
        "--export-debug-html",
        action="store_true",
        help="Generate output_dir/debug_view.html from units_final.jsonl and scenes.jsonl",
    )
    args = parser.parse_args()

    report = run_pipeline(
        args.epub_path,
        args.output_dir,
        model=args.model,
        max_scene_blocks=args.max_scene_blocks,
        context_prev=args.context_prev,
        context_next=args.context_next,
        confidence_threshold=args.confidence_threshold,
        resume=args.resume,
        chapter_filter=args.chapter_filter,
        max_scenes=args.max_scenes,
        dry_run_no_llm=args.dry_run_no_llm,
        export_debug_html=args.export_debug_html,
    )
    print(
        f"done scenes={report['scenes']} target={report['target_scenes']} units_final={report['units_final']} errors={report['scene_errors']}"
    )


if __name__ == "__main__":
    main()
