from __future__ import annotations

import re
import unicodedata


_RUBY_PATTERN = re.compile(r"<ruby\b[^>]*>(.*?)</ruby>", re.IGNORECASE | re.DOTALL)
_RT_CONTENT_PATTERN = re.compile(r"<rt\b[^>]*>(.*?)</rt>", re.IGNORECASE | re.DOTALL)
_RT_PATTERN = re.compile(r"<rt\b[^>]*>.*?</rt>", re.IGNORECASE | re.DOTALL)
_RP_PATTERN = re.compile(r"<rp\b[^>]*>.*?</rp>", re.IGNORECASE | re.DOTALL)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_INVISIBLE_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff]")


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
      ruby_map: list of base/reading pairs in appearance order
    """

    ruby_map: list[dict[str, str]] = []

    def _ruby_to_text(match: re.Match[str]) -> str:
        body = match.group(1)
        base = _RT_PATTERN.sub("", body)
        base = _RP_PATTERN.sub("", base)
        base = _normalize_surface_text(base)
        reading_parts = [_normalize_surface_text(x) for x in _RT_CONTENT_PATTERN.findall(body)]
        reading = "".join([p for p in reading_parts if p])
        if reading:
            ruby_map.append({"base": base, "reading": reading})
            return f"{base}({reading})"
        return base

    text_with_ruby = _RUBY_PATTERN.sub(_ruby_to_text, html)
    text_with_ruby = _normalize_surface_text(text_with_ruby)

    def _ruby_to_base(match: re.Match[str]) -> str:
        body = match.group(1)
        body = _RT_PATTERN.sub("", body)
        body = _RP_PATTERN.sub("", body)
        return body

    text = _RUBY_PATTERN.sub(_ruby_to_base, html)
    text = _normalize_surface_text(text)

    return {
        "text": text,
        "text_with_ruby": text_with_ruby,
        "ruby_map": ruby_map,
    }


def normalize_html_block(html: str) -> str:
    """Backwards-compatible text normalizer."""

    return extract_text_fields(html)["text"]
