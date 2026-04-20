from __future__ import annotations

import re
import unicodedata


_RUBY_PATTERN = re.compile(r"<ruby\b[^>]*>(.*?)</ruby>", re.IGNORECASE | re.DOTALL)
_RT_CONTENT_PATTERN = re.compile(r"<rt\b[^>]*>(.*?)</rt>", re.IGNORECASE | re.DOTALL)
_RT_PATTERN = re.compile(r"<rt\b[^>]*>.*?</rt>", re.IGNORECASE | re.DOTALL)
_RP_PATTERN = re.compile(r"<rp\b[^>]*>.*?</rp>", re.IGNORECASE | re.DOTALL)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_INVISIBLE_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_RUBY_POS_PATTERN = re.compile(r"\ue000(\d+)\ue001(.*?)\ue000/\1\ue001", re.DOTALL)


def _normalize_surface_text(s: str) -> str:
    s = _TAG_PATTERN.sub("", s)
    s = _INVISIBLE_PATTERN.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_text_fields(html: str) -> dict:
    """Extract plain text and ruby-preserving text from one html block.

    Returns:
      text: ruby annotations removed (surface/base text only)
      text_with_ruby: ruby annotations inlined as ``base(reading)``
      ruby_map: list of ruby spans in appearance order
    """

    ruby_pairs: list[dict[str, str | int]] = []

    def _ruby_to_text(match: re.Match[str]) -> str:
        body = match.group(1)
        base = _RT_PATTERN.sub("", body)
        base = _RP_PATTERN.sub("", base)
        base = _normalize_surface_text(base)
        reading_parts = [_normalize_surface_text(x) for x in _RT_CONTENT_PATTERN.findall(body)]
        rt = "".join([p for p in reading_parts if p])
        if rt:
            ruby_pairs.append({"base": base, "rt": rt, "start": -1, "end": -1})
            return f"{base}({rt})"
        return base

    text_with_ruby = _RUBY_PATTERN.sub(_ruby_to_text, html)
    text_with_ruby = _normalize_surface_text(text_with_ruby)

    ruby_marker_index = 0

    def _ruby_to_base_with_marker(match: re.Match[str]) -> str:
        nonlocal ruby_marker_index
        body = match.group(1)
        base = _RT_PATTERN.sub("", body)
        base = _RP_PATTERN.sub("", base)
        base = _normalize_surface_text(base)
        reading_parts = [_normalize_surface_text(x) for x in _RT_CONTENT_PATTERN.findall(body)]
        rt = "".join([p for p in reading_parts if p])
        if not rt:
            return base
        ruby_index = ruby_marker_index
        ruby_marker_index += 1
        marker_start = f"\ue000{ruby_index}\ue001"
        marker_end = f"\ue000/{ruby_index}\ue001"
        return f"{marker_start}{base}{marker_end}"

    marked_text = _RUBY_PATTERN.sub(_ruby_to_base_with_marker, html)
    marked_text = _normalize_surface_text(marked_text)

    ruby_map: list[dict[str, str | int]] = [dict(pair) for pair in ruby_pairs]
    text_parts: list[str] = []
    cursor = 0
    plain_len = 0
    for m in _RUBY_POS_PATTERN.finditer(marked_text):
        prefix = marked_text[cursor : m.start()]
        text_parts.append(prefix)
        plain_len += len(prefix)
        ruby_index = int(m.group(1))
        base = m.group(2)
        text_parts.append(base)
        if 0 <= ruby_index < len(ruby_map):
            ruby_map[ruby_index]["base"] = base
            ruby_map[ruby_index]["start"] = plain_len
            ruby_map[ruby_index]["end"] = plain_len + len(base)
        plain_len += len(base)
        cursor = m.end()
    text_parts.append(marked_text[cursor:])
    text = "".join(text_parts)

    return {
        "text": text,
        "surface_text": text,
        "normalized_text": text,
        "text_with_ruby": text_with_ruby,
        "ruby_map": ruby_map,
    }


def normalize_html_block(html: str) -> str:
    """Backwards-compatible text normalizer."""

    return extract_text_fields(html)["text"]
