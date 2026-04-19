from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Callable

_NAME_PATTERN = re.compile(r"[A-Z][a-z]{1,20}|[\u3040-\u30ff\u4e00-\u9fff]{2,8}")
_CASE_PARTICLE_PATTERN = re.compile(
    r"([A-Z][a-z]{1,20}|[\u3040-\u30ff\u4e00-\u9fff]{1,10}?)(?=(?:は|が|に|と))(?:は|が|に|と)"
)
_CALLING_PATTERN = re.compile(
    r"([A-Z][a-z]{1,20}|[\u3040-\u30ff\u4e00-\u9fff]{1,10})(?:さん|君|くん|ちゃん|様|兄ちゃん|姉ちゃん|お兄ちゃん|お姉ちゃん)"
)
_RESERVED = {"narrator", "unknown"}

UnknownIdHook = Callable[[str, str, dict[str, int]], str]


def default_unknown_scene_local_id(name_hint: str, scene_id: str, counters: dict[str, int]) -> str:
    """Assign a scene-local id for unknown/temporary characters.

    This hook is intentionally simple and can be replaced by callers.
    """

    hint = name_hint.strip()
    if not hint:
        base = "mob"
    elif any(token in hint for token in ("店", "店員", "master", "マスター")):
        base = "shopkeeper"
    elif any(token in hint for token in ("男", "兄", "お兄")):
        base = "mob_male"
    elif any(token in hint for token in ("女", "姉", "お姉")):
        base = "mob_female"
    else:
        base = "mob"

    counters[base] = counters.get(base, 0) + 1
    return f"{base}_{counters[base]}"


def extract_case_particle_mentions(text: str) -> list[str]:
    """Extract `Xは/Xが/Xに/Xと` style subject/object mentions from text."""

    mentions: list[str] = []
    for m in _CASE_PARTICLE_PATTERN.findall(text or ""):
        name = m.strip()
        if name and name.lower() not in _RESERVED:
            mentions.append(name)
    return mentions


def extract_calling_mentions(text: str) -> list[str]:
    """Extract simple calling forms like `〜さん`, `兄ちゃん` from text."""

    mentions: list[str] = []
    for m in _CALLING_PATTERN.findall(text or ""):
        name = m.strip()
        if name and name.lower() not in _RESERVED:
            mentions.append(name)
    return mentions


def _collect_nearby_hints(unit: dict) -> list[str]:
    texts = [
        str(unit.get("prev_context") or ""),
        str(unit.get("surface_text") or unit.get("text") or ""),
        str(unit.get("next_context") or ""),
    ]
    hints: list[str] = []
    for text in texts:
        hints.extend(extract_case_particle_mentions(text))
        hints.extend(extract_calling_mentions(text))
    return hints


def _to_character_entry(char_id: str, display_name: str, aliases: set[str] | None = None) -> dict:
    return {
        "id": char_id,
        "display_name": display_name,
        "aliases": sorted(aliases or []),
    }


def build_characters(
    units: list[dict],
    *,
    unknown_id_hook: UnknownIdHook | None = None,
) -> list[dict]:
    """Build characters.json-compatible candidate set for one scene.

    Output schema: `[{id, display_name, aliases}, ...]`.
    Always includes `narrator` and `unknown`.
    """

    counter: Counter[str] = Counter()
    alias_map: dict[str, set[str]] = defaultdict(set)
    scene_id = str(units[0].get("scene_id") or "scene") if units else "scene"
    hook = unknown_id_hook or default_unknown_scene_local_id
    local_counters: dict[str, int] = {}

    for unit in units:
        text = str(unit.get("surface_text") or unit.get("text") or "")
        for m in _NAME_PATTERN.findall(text):
            name = m.strip()
            if not name or name.lower() in _RESERVED:
                continue
            counter[name] += 1
            alias_map[name.lower()].add(name)

        for hint in _collect_nearby_hints(unit):
            counter[hint] += 1
            alias_map[hint.lower()].add(hint)

    characters = [
        _to_character_entry("narrator", "narrator"),
        _to_character_entry("unknown", "unknown"),
    ]

    for name, _ in counter.most_common(200):
        canonical = name.lower()
        if canonical in _RESERVED:
            continue
        characters.append(
            _to_character_entry(
                canonical,
                name,
                aliases=alias_map.get(canonical, set()),
            )
        )

    # hook point: assign scene-local IDs for candidates that remain unknown-ish.
    for unit in units:
        if str(unit.get("speaker") or "") != "unknown":
            continue
        for hint in _collect_nearby_hints(unit):
            unknown_id = hook(hint, scene_id, local_counters)
            if all(c["id"] != unknown_id for c in characters):
                characters.append(_to_character_entry(unknown_id, hint, aliases={hint}))

    return characters
