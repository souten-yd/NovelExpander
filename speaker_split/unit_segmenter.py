from __future__ import annotations

import re


_QUOTE_CHARS = "「『“\""
_NONVERBAL_PATTERNS = [
    re.compile(r"^[（(].+[）)]$"),
    re.compile(r"^(?:……|…|\.{3,}|\*+|！？|!?)+$"),
]


def _is_dialogue(text: str) -> bool:
    t = text.strip()
    return t[:1] in _QUOTE_CHARS and ("」" in t or "』" in t or "\"" in t)


def _is_nonverbal(text: str) -> bool:
    t = text.strip()
    return any(p.match(t) for p in _NONVERBAL_PATTERNS)


def _split_mixed_paragraph(text: str) -> list[str]:
    # Split when quoted dialogue is followed/preceded by narration.
    chunks = [c.strip() for c in re.split(r"(?<=」)|(?=「)", text) if c.strip()]
    if len(chunks) == 1:
        return chunks
    return chunks


def segment_scene_units(scene: dict) -> list[dict]:
    units: list[dict] = []
    idx = 0
    for block in scene.get("blocks", []):
        text = (block.get("text") or "").strip()
        if not text:
            continue
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        for para in paragraphs:
            for chunk in _split_mixed_paragraph(para):
                if _is_nonverbal(chunk):
                    label = "nonverbal"
                elif _is_dialogue(chunk):
                    label = "dialogue"
                else:
                    label = "narration"
                units.append(
                    {
                        "scene_id": scene.get("scene_id"),
                        "unit_id": f"{scene.get('scene_id')}_u{idx:04d}",
                        "text": chunk,
                        "pass1_label": label,
                    }
                )
                idx += 1
    return units
