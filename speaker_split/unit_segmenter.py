from __future__ import annotations

import re


_QUOTE_CHARS = "「『“\""


def segment_scene_units(scene: dict) -> list[dict]:
    units: list[dict] = []
    idx = 0
    for block in scene.get("blocks", []):
        text = (block.get("text") or "").strip()
        if not text:
            continue
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        for para in paragraphs:
            label = "dialogue" if para[:1] in _QUOTE_CHARS else "narration"
            units.append(
                {
                    "scene_id": scene.get("scene_id"),
                    "unit_id": f"{scene.get('scene_id')}_u{idx:04d}",
                    "text": para,
                    "pass1_label": label,
                }
            )
            idx += 1
    return units
