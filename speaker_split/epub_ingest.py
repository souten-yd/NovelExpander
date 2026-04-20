from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
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
    tag: str
    is_meta: bool


_META_PATTERN = re.compile(r"^(?:目次|奥付|まえがき|あとがき|copyright|contents?)$", re.IGNORECASE)
_META_URL_PATTERN = re.compile(r"^(?:https?://|www\.)", re.IGNORECASE)
_META_PUBLISHING_PATTERN = re.compile(r"(?:発行|発刊|初版|版|掲載情報)")


def _strip_tags(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def is_meta_text(tag: str, text: str) -> bool:
    normalized = text.strip()
    if tag.lower() not in {"h1", "h2", "h3"}:
        return False
    if _META_PATTERN.match(normalized):
        return True
    if _META_URL_PATTERN.match(normalized):
        return True
    if _META_PUBLISHING_PATTERN.search(normalized):
        return True
    return False


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

    base_dir = PurePosixPath(opf_path).parent

    ordered_docs: list[str] = []
    for itemref in spine.findall("{*}itemref"):
        item_idref = itemref.attrib.get("idref")
        if not item_idref:
            continue
        href = id_to_href.get(item_idref)
        if not href:
            continue
        href_path = href.split("#", 1)[0]
        resolved = PurePosixPath(href_path)
        if not resolved.is_absolute():
            resolved = base_dir / resolved
        ordered_docs.append(str(resolved))
    return ordered_docs


def iter_spine_documents(epub_path: str | Path) -> Iterator[tuple[str, str]]:
    """Yield (source_file, html) in spine order."""

    with zipfile.ZipFile(epub_path) as zf:
        opf_path = _resolve_opf_path(zf)
        doc_paths = _read_spine_doc_hrefs(zf, opf_path)
        for doc_path in doc_paths:
            try:
                html = zf.read(doc_path).decode("utf-8", errors="ignore")
            except KeyError:
                continue
            yield doc_path, html


def extract_raw_blocks(epub_path: str | Path) -> list[RawBlock]:
    """Extract minimally split blocks from heading/paragraph/hr tags."""

    blocks: list[RawBlock] = []
    pattern = re.compile(r"<(h1|h2|h3|p|hr)\b[^>]*>(.*?)</\1>|<(hr)\b[^>]*/?>", re.IGNORECASE | re.DOTALL)
    for doc_id, html in iter_spine_documents(epub_path):
        i = 0
        for m in re.finditer(pattern, html):
            tag = (m.group(1) or m.group(3) or "").lower()
            chunk = m.group(0)
            text = "---" if tag == "hr" else _strip_tags(chunk)
            if not text:
                continue
            blocks.append(
                RawBlock(
                    doc_id=doc_id,
                    order=i,
                    html=chunk,
                    text=text,
                    tag=tag,
                    is_meta=is_meta_text(tag, text),
                )
            )
            i += 1
        if i == 0:
            text = _strip_tags(html)
            if text:
                blocks.append(
                    RawBlock(doc_id=doc_id, order=0, html=html, text=text, tag="doc", is_meta=is_meta_text("doc", text))
                )
    return blocks
