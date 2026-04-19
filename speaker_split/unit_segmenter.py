from __future__ import annotations

import re

_QUOTE_OPEN = "「『“\""
_QUOTE_CLOSE = "」』”\""
_SENTENCE_BOUNDARY = "。！？!?…」』）)]】"
_NONVERBAL_PATTERNS = [
    re.compile(r"^(?:……|…|\.{3,}|\*+|！？|!?)+$"),
]
_NONVERBAL_ACTION_WORDS = (
    "頷",
    "うなず",
    "ため息",
    "息",
    "笑",
    "泣",
    "沈黙",
    "無言",
)


def _normalize_text(text: str) -> str:
    t = text.replace("\u3000", " ")
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return t.strip()


def _is_dialogue(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    return t[:1] in _QUOTE_OPEN and t[-1:] in _QUOTE_CLOSE


def _is_nonverbal(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if any(p.match(t) for p in _NONVERBAL_PATTERNS):
        return True
    if t.startswith(("（", "(")) and t.endswith(("）", ")")):
        inner = t[1:-1].strip()
        if len(inner) <= 8 or any(w in inner for w in _NONVERBAL_ACTION_WORDS):
            return True
    return False


def _is_monologue(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if t.startswith(("（", "(")) and t.endswith(("）", ")")):
        inner = t[1:-1].strip()
        if inner and not _is_nonverbal(t):
            return True
    if t.startswith(("――", "…")) and len(t) >= 6:
        return True
    return False


def _is_meta(chunk: str, block: dict) -> bool:
    block_type = str(block.get("block_type") or "").lower()
    if bool(block.get("is_meta")):
        return True
    return block_type in {"meta", "heading"}


def _find_quoted_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []
    pairs = {"「": "」", "『": "』", "“": "”", '"': '"'}
    for i, ch in enumerate(text):
        if ch in pairs:
            stack.append((ch, i))
            continue
        if not stack:
            continue
        open_ch, start = stack[-1]
        if ch == pairs[open_ch]:
            stack.pop()
            if not stack:
                spans.append((start, i + 1))
    return spans


def _has_boundary(text: str, index: int, *, backward: bool) -> bool:
    if backward:
        i = index - 1
        while i >= 0 and text[i].isspace():
            i -= 1
        if i < 0:
            return True
        return text[i] in _SENTENCE_BOUNDARY

    i = index
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i >= n:
        return True
    return text[i] in "「『" or text[i] in _SENTENCE_BOUNDARY


def _split_mixed_paragraph(text: str) -> list[str]:
    spans = _find_quoted_spans(text)
    if not spans:
        stripped = text.strip()
        return [stripped] if stripped else []

    cut_points = {0, len(text)}
    for start, end in spans:
        boundary_split = _has_boundary(text, start, backward=True) and _has_boundary(text, end, backward=False)
        edge_split = start == 0 or end == len(text)
        if boundary_split or edge_split:
            cut_points.add(start)
            cut_points.add(end)

    points = sorted(cut_points)
    chunks: list[str] = []
    for i in range(len(points) - 1):
        chunk = text[points[i] : points[i + 1]].strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def _label_unit(chunk: str, block: dict) -> str:
    if _is_meta(chunk, block):
        return "meta"
    if _is_nonverbal(chunk):
        return "nonverbal"
    if _is_dialogue(chunk):
        return "dialogue"
    if _is_monologue(chunk):
        return "monologue"
    return "narration"


def segment_scene_units(scene: dict) -> list[dict]:
    units: list[dict] = []
    scene_id = str(scene.get("scene_id") or "")

    for block_index, block in enumerate(scene.get("blocks", [])):
        raw_text = str(block.get("text") or "")
        if not raw_text.strip():
            continue

        paragraphs = [p.strip() for p in re.split(r"\n{2,}", raw_text) if p.strip()]
        for para in paragraphs:
            for chunk in _split_mixed_paragraph(para):
                unit_type = _label_unit(chunk, block)
                units.append(
                    {
                        "scene_id": scene_id,
                        "surface_text": chunk,
                        "normalized_text": _normalize_text(chunk),
                        "unit_type": unit_type,
                        "pass1_label": unit_type,
                        "mode": "narrative" if unit_type in {"narration", "monologue", "meta"} else "utterance",
                        "speaker": "narrator" if unit_type == "narration" else "unknown",
                        "speaker_canonical_id": "narrator" if unit_type == "narration" else "unknown",
                        "speaker_candidates": [],
                        "confidence": 0.0,
                        "evidence": "pass1_rule_based",
                        "alternatives": [],
                        "post_resolve_actions": [],
                        "source_indexes": list(block.get("source_indexes") or [block_index]),
                        "source_file": block.get("source_file"),
                        "raw_html": block.get("raw_html"),
                        "chapter_title": block.get("chapter_title"),
                    }
                )

    for order_in_scene, unit in enumerate(units):
        unit["order_in_scene"] = order_in_scene
        unit["unit_id"] = f"{scene_id}_u{order_in_scene:04d}"

    for i, unit in enumerate(units):
        unit["prev_context"] = units[i - 1]["surface_text"] if i > 0 else ""
        unit["next_context"] = units[i + 1]["surface_text"] if i + 1 < len(units) else ""

    return units
