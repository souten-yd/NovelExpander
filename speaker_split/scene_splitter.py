from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(slots=True)
class Scene:
    scene_id: str
    blocks: list[dict]


_BOUNDARY_PATTERN = re.compile(r"^(\*{3,}|[-―]{3,}|#|第[0-9一二三四五六七八九十百]+章)")


def split_scenes(normalized_blocks: list[dict]) -> list[Scene]:
    scenes: list[Scene] = []
    current: list[dict] = []

    def flush() -> None:
        if not current:
            return
        scene_id = f"scene_{len(scenes)+1:04d}"
        scenes.append(Scene(scene_id=scene_id, blocks=current.copy()))
        current.clear()

    for block in normalized_blocks:
        text = (block.get("text") or "").strip()
        if not text:
            continue
        if _BOUNDARY_PATTERN.match(text) and current:
            flush()
        current.append(block)

    flush()
    return scenes
