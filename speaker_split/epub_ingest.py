from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import re
import zipfile
import xml.etree.ElementTree as ET


@dataclass(slots=True)
class RawBlock:
    """Raw text block extracted from EPUB documents."""

    doc_id: str
    order: int
    html: str
    text: str


def _strip_tags(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _resolve_opf_path(zf: zipfile.ZipFile) -> str:
    container = zf.read("META-INF/container.xml")
    root = ET.fromstring(container)
    node = root.find(".//{*}rootfile")
    if node is None:
        raise ValueError("container.xml has no rootfile")
    full_path = node.attrib.get("full-path")
    if not full_path:
        raise ValueError("container.xml rootfile missing full-path")
    return full_path


def _read_spine_doc_hrefs(zf: zipfile.ZipFile, opf_path: str) -> list[str]:
    opf_bytes = zf.read(opf_path)
    package = ET.fromstring(opf_bytes)
    manifest = package.find(".//{*}manifest")
    spine = package.find(".//{*}spine")
    if manifest is None or spine is None:
        raise ValueError("OPF missing manifest/spine")

    id_to_href: dict[str, str] = {}
    for item in manifest.findall("{*}item"):
        item_id = item.attrib.get("id")
        href = item.attrib.get("href")
        media_type = item.attrib.get("media-type", "")
        if item_id and href and ("html" in media_type or href.endswith((".xhtml", ".html", ".htm"))):
            id_to_href[item_id] = href

    base = str(Path(opf_path).parent)
    if base == ".":
        base = ""
    else:
        base = f"{base}/"

    ordered_docs: list[str] = []
    for itemref in spine.findall("{*}itemref"):
        item_idref = itemref.attrib.get("idref")
        if not item_idref:
            continue
        href = id_to_href.get(item_idref)
        if not href:
            continue
        ordered_docs.append(f"{base}{href}")
    return ordered_docs


def iter_spine_documents(epub_path: str | Path) -> Iterator[tuple[str, str]]:
    """Yield (doc_id, html) in spine order."""

    with zipfile.ZipFile(epub_path) as zf:
        opf_path = _resolve_opf_path(zf)
        doc_paths = _read_spine_doc_hrefs(zf, opf_path)
        for idx, doc_path in enumerate(doc_paths):
            try:
                html = zf.read(doc_path).decode("utf-8", errors="ignore")
            except KeyError:
                continue
            yield f"doc_{idx:04d}", html


def extract_raw_blocks(epub_path: str | Path) -> list[RawBlock]:
    """Extract minimally split blocks from paragraph-like tags."""

    blocks: list[RawBlock] = []
    pattern = re.compile(r"<(p|div|li|h[1-6])\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
    for doc_id, html in iter_spine_documents(epub_path):
        # findall with group loses full match; use finditer for content
        i = 0
        for m in re.finditer(pattern, html):
            chunk = m.group(0)
            text = _strip_tags(chunk)
            if not text:
                continue
            blocks.append(RawBlock(doc_id=doc_id, order=i, html=chunk, text=text))
            i += 1
        if i == 0:
            text = _strip_tags(html)
            if text:
                blocks.append(RawBlock(doc_id=doc_id, order=0, html=html, text=text))
    return blocks
