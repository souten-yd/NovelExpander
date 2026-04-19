from __future__ import annotations

import re
from collections import Counter


_NAME_PATTERN = re.compile(r"[A-Z][a-z]{1,20}|[\u3040-\u30ff\u4e00-\u9fff]{2,8}")
_RESERVED = {"narrator", "unknown"}


def build_characters(units: list[dict]) -> list[dict]:
    counter: Counter[str] = Counter()
    for unit in units:
        for m in _NAME_PATTERN.findall(unit.get("text", "")):
            name = m.strip()
            if not name or name in _RESERVED:
                continue
            counter[name] += 1

    characters = [
        {"canonical": "narrator", "display": "narrator", "count": 0},
        {"canonical": "unknown", "display": "unknown", "count": 0},
    ]

    for name, c in counter.most_common(200):
        canonical = name.lower()
        if canonical in _RESERVED:
            continue
        characters.append({"canonical": canonical, "display": name, "count": c})
    return characters
