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
    "speaker_candidates",
    "alternatives",
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
    speaker_candidates = unit.get("speaker_candidates")
    if speaker_candidates is not None:
        out["speaker_candidates"] = json.dumps(speaker_candidates, ensure_ascii=False)
    alternatives = unit.get("alternatives")
    if alternatives is not None:
        out["alternatives"] = json.dumps(alternatives, ensure_ascii=False)
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
    .controls {{ display: flex; flex-wrap: wrap; gap: 16px 24px; margin-bottom: 12px; align-items: center; }}
    .controls input[type="number"] {{ width: 8em; }}
    table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
    th, td {{ border: 1px solid #ccc; padding: 6px; vertical-align: top; word-break: break-word; }}
    thead th {{ position: sticky; top: 0; background: #fff; z-index: 1; }}
    td.col-surface_text, td.col-normalized_text, td.col-prev_context, td.col-next_context {{ white-space: pre-wrap; }}
    td.col-source_file, td.col-source_indexes {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .speaker-select {{ width: 100%; }}
    .trace-wrap {{ display: flex; gap: 6px; align-items: center; }}
    .trace-text {{ overflow-wrap: anywhere; }}
    .copy-btn {{ font-size: 12px; padding: 1px 6px; }}
    .status {{ color: #555; font-size: 0.9em; }}
  </style>
</head>
<body>
  <h1>speaker_split debug view</h1>
  <div class=\"controls\">
    <label><input id=\"onlyUnknown\" type=\"checkbox\" /> unknownのみ</label>
    <label><input id=\"sortConfidence\" type=\"checkbox\" /> confidence昇順</label>
    <label>confidence上限: <input id=\"maxConfidence\" type=\"number\" step=\"0.01\" placeholder=\"例: 0.6\" /></label>
    <button id=\"downloadJson\" type=\"button\">修正結果JSONをダウンロード</button>
    <span id=\"downloadStatus\" class=\"status\"></span>
  </div>
  <table>
    <thead><tr><th>speaker_edit</th>{header}</tr></thead>
    <tbody id=\"rows\"></tbody>
  </table>
  <script>
    const COLUMNS = {json.dumps(_COLUMNS)};
    const ROWS = {rows_json}.map((row, idx) => ({{ ...row, __rowId: idx }}));
    const editedSpeakers = new Map();

    function normalizeConfidence(value) {{
      const num = Number(value);
      return Number.isFinite(num) ? num : Number.POSITIVE_INFINITY;
    }}

    function speakerOptions(row) {{
      const candidates = [];
      const baseSpeaker = (row.speaker ?? '').toString();
      if (baseSpeaker) {{
        candidates.push(baseSpeaker);
      }}
      for (const field of ['speaker_candidates', 'alternatives']) {{
        try {{
          const parsed = JSON.parse(row[field] || 'null');
          if (Array.isArray(parsed)) {{
            for (const entry of parsed) {{
              if (typeof entry === 'string') {{
                candidates.push(entry);
              }} else if (entry && typeof entry === 'object') {{
                const v = entry.speaker ?? entry.name ?? entry.label ?? entry.id;
                if (v != null) {{
                  candidates.push(String(v));
                }}
              }}
            }}
          }}
        }} catch (_err) {{
          // ignore parse errors and fallback to free text row values
        }}
      }}
      if (!candidates.length) {{
        candidates.push('unknown');
      }}
      return [...new Set(candidates.filter(Boolean))];
    }}

    function applyFilters(baseRows) {{
      let output = [...baseRows];
      if (document.getElementById('onlyUnknown').checked) {{
        output = output.filter(
          (row) => ((editedSpeakers.get(row.__rowId) || row.speaker || '').toLowerCase() === 'unknown'),
        );
      }}
      const maxConfidenceRaw = document.getElementById('maxConfidence').value.trim();
      if (maxConfidenceRaw !== '') {{
        const maxConfidence = Number(maxConfidenceRaw);
        if (Number.isFinite(maxConfidence)) {{
          output = output.filter((row) => normalizeConfidence(row.confidence) <= maxConfidence);
        }}
      }}
      if (document.getElementById('sortConfidence').checked) {{
        output.sort((a, b) => normalizeConfidence(a.confidence) - normalizeConfidence(b.confidence));
      }}
      return output;
    }}

    function copyText(value) {{
      navigator.clipboard.writeText(value).catch(() => {{
        // noop: clipboard may be blocked by browser policy
      }});
    }}

    function renderRows() {{
      const tbody = document.getElementById('rows');
      tbody.innerHTML = '';
      const rows = applyFilters(ROWS);
      for (const row of rows) {{
        const tr = document.createElement('tr');

        const editTd = document.createElement('td');
        const select = document.createElement('select');
        select.className = 'speaker-select';
        const selectedSpeaker = editedSpeakers.get(row.__rowId) || row.speaker || 'unknown';
        for (const optionValue of speakerOptions(row)) {{
          const option = document.createElement('option');
          option.value = optionValue;
          option.textContent = optionValue;
          option.selected = optionValue === selectedSpeaker;
          select.appendChild(option);
        }}
        select.addEventListener('change', (event) => {{
          editedSpeakers.set(row.__rowId, event.target.value);
          row.speaker = event.target.value;
          renderRows();
        }});
        editTd.appendChild(select);
        tr.appendChild(editTd);

        for (const col of COLUMNS) {{
          const td = document.createElement('td');
          td.className = `col-${{col}}`;
          if (col === 'source_file' || col === 'source_indexes') {{
            const text = (row[col] ?? '').toString();
            const wrap = document.createElement('div');
            wrap.className = 'trace-wrap';
            const textNode = document.createElement('span');
            textNode.className = 'trace-text';
            textNode.textContent = text;
            const copyBtn = document.createElement('button');
            copyBtn.type = 'button';
            copyBtn.className = 'copy-btn';
            copyBtn.textContent = 'copy';
            copyBtn.addEventListener('click', () => copyText(text));
            wrap.appendChild(textNode);
            wrap.appendChild(copyBtn);
            td.appendChild(wrap);
          }} else {{
            td.textContent = row[col] ?? '';
          }}
          tr.appendChild(td);
        }}
        tbody.appendChild(tr);
      }}
    }}

    function downloadEditedRows() {{
      const payload = ROWS.map((row) => {{
        const speaker = editedSpeakers.get(row.__rowId) || row.speaker || 'unknown';
        return {{
          row_id: row.__rowId,
          scene_id: row.scene_id,
          normalized_text: row.normalized_text,
          speaker,
          source_file: row.source_file,
          source_indexes: row.source_indexes,
        }};
      }});
      const blob = new Blob([JSON.stringify(payload, null, 2)], {{ type: 'application/json' }});
      const url = URL.createObjectURL(blob);
      const now = new Date().toISOString().replace(/[:.]/g, '-');
      const a = document.createElement('a');
      a.href = url;
      a.download = `speaker-edits-${{now}}.json`;
      a.click();
      URL.revokeObjectURL(url);
      document.getElementById('downloadStatus').textContent = `${{payload.length}}件を書き出しました`;
    }}

    document.getElementById('onlyUnknown').addEventListener('change', renderRows);
    document.getElementById('sortConfidence').addEventListener('change', renderRows);
    document.getElementById('maxConfidence').addEventListener('input', renderRows);
    document.getElementById('downloadJson').addEventListener('click', downloadEditedRows);
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
