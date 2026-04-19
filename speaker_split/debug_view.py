from __future__ import annotations

import json
from html import escape
from pathlib import Path


_COLUMNS = [
    "chapter_title",
    "scene_id",
    "surface_text",
    "normalized_text",
    "unit_type",
    "speaker",
    "confidence",
    "evidence",
    "source_file",
    "source_indexes",
    "prev_context",
    "next_context",
]


def _read_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _scene_meta_by_scene_id(scenes: list[dict]) -> dict[str, dict]:
    meta: dict[str, dict] = {}
    for scene in scenes:
        scene_id = scene.get("scene_id")
        blocks = scene.get("blocks") or []
        first_block = blocks[0] if blocks else {}
        chapter_title = first_block.get("chapter_title") or ""
        source_file = first_block.get("source_file") or ""
        source_indexes = first_block.get("source_indexes") or []
        prev_context = blocks[0].get("text") if len(blocks) > 0 else ""
        next_context = blocks[-1].get("text") if len(blocks) > 1 else ""
        meta[scene_id] = {
            "chapter_title": chapter_title,
            "source_file": source_file,
            "source_indexes": source_indexes,
            "prev_context": prev_context or "",
            "next_context": next_context or "",
        }
    return meta


def _normalize_row(unit: dict, scene_meta: dict) -> dict:
    out: dict[str, str] = {}
    for col in _COLUMNS:
        out[col] = ""

    scene_id = str(unit.get("scene_id") or "")
    meta = scene_meta.get(scene_id, {})

    out["chapter_title"] = str(unit.get("chapter_title") or meta.get("chapter_title") or "")
    out["scene_id"] = scene_id
    out["surface_text"] = str(unit.get("surface_text") or unit.get("text") or "")
    out["normalized_text"] = str(unit.get("normalized_text") or unit.get("text") or "")
    out["unit_type"] = str(unit.get("unit_type") or unit.get("pass1_label") or "")
    out["speaker"] = str(unit.get("speaker") or "unknown")
    out["confidence"] = str(unit.get("confidence") if unit.get("confidence") is not None else "")
    out["evidence"] = str(unit.get("evidence") or "")
    out["source_file"] = str(unit.get("source_file") or meta.get("source_file") or "")

    source_indexes = unit.get("source_indexes")
    if source_indexes is None:
        source_indexes = meta.get("source_indexes") or []
    out["source_indexes"] = ",".join(str(v) for v in source_indexes)

    out["prev_context"] = str(unit.get("prev_context") or meta.get("prev_context") or "")
    out["next_context"] = str(unit.get("next_context") or meta.get("next_context") or "")
    return out


def build_debug_html(units_final_path: str | Path, scenes_path: str | Path) -> str:
    units = _read_jsonl(units_final_path)
    scenes = _read_jsonl(scenes_path)
    scene_meta = _scene_meta_by_scene_id(scenes)

    rows = [_normalize_row(unit, scene_meta) for unit in units]
    rows_json = json.dumps(rows, ensure_ascii=False)

    header = "".join(f"<th>{escape(col)}</th>" for col in _COLUMNS)

    return f"""<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>speaker_split debug view</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 16px; }}
    .controls {{ display: flex; gap: 24px; margin-bottom: 12px; }}
    table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
    th, td {{ border: 1px solid #ccc; padding: 6px; vertical-align: top; word-break: break-word; }}
    thead th {{ position: sticky; top: 0; background: #fff; z-index: 1; }}
    td.col-surface_text, td.col-normalized_text, td.col-prev_context, td.col-next_context {{ white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>speaker_split debug view</h1>
  <div class=\"controls\">
    <label><input id=\"onlyUnknown\" type=\"checkbox\" /> unknownのみ</label>
    <label><input id=\"sortConfidence\" type=\"checkbox\" /> confidence昇順</label>
  </div>
  <table>
    <thead><tr>{header}</tr></thead>
    <tbody id=\"rows\"></tbody>
  </table>
  <script>
    const COLUMNS = {json.dumps(_COLUMNS)};
    const ROWS = {rows_json};

    function normalizeConfidence(value) {{
      const num = Number(value);
      return Number.isFinite(num) ? num : Number.POSITIVE_INFINITY;
    }}

    function applyFilters(baseRows) {{
      let output = [...baseRows];
      if (document.getElementById('onlyUnknown').checked) {{
        output = output.filter((row) => (row.speaker || '').toLowerCase() === 'unknown');
      }}
      if (document.getElementById('sortConfidence').checked) {{
        output.sort((a, b) => normalizeConfidence(a.confidence) - normalizeConfidence(b.confidence));
      }}
      return output;
    }}

    function renderRows() {{
      const tbody = document.getElementById('rows');
      tbody.innerHTML = '';
      const rows = applyFilters(ROWS);
      for (const row of rows) {{
        const tr = document.createElement('tr');
        for (const col of COLUMNS) {{
          const td = document.createElement('td');
          td.className = `col-${{col}}`;
          td.textContent = row[col] ?? '';
          tr.appendChild(td);
        }}
        tbody.appendChild(tr);
      }}
    }}

    document.getElementById('onlyUnknown').addEventListener('change', renderRows);
    document.getElementById('sortConfidence').addEventListener('change', renderRows);
    renderRows();
  </script>
</body>
</html>
"""


def write_debug_html(units_final_path: str | Path, scenes_path: str | Path, output_path: str | Path) -> Path:
    html = build_debug_html(units_final_path, scenes_path)
    p = Path(output_path)
    p.write_text(html, encoding="utf-8")
    return p
