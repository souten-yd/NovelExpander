from __future__ import annotations

import re
import unicodedata


_RUBY_PATTERN = re.compile(r"<ruby\b[^>]*>(.*?)</ruby>", re.IGNORECASE | re.DOTALL)
_RT_PATTERN = re.compile(r"<rt\b[^>]*>.*?</rt>", re.IGNORECASE | re.DOTALL)
_RP_PATTERN = re.compile(r"<rp\b[^>]*>.*?</rp>", re.IGNORECASE | re.DOTALL)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_INVISIBLE_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff]")


def normalize_html_block(html: str) -> str:
    """Handle ruby/invisible chars and normalize unicode."""

    def _ruby_to_base(match: re.Match[str]) -> str:
        body = match.group(1)
        body = _RT_PATTERN.sub("", body)
        body = _RP_PATTERN.sub("", body)
        return body

    s = _RUBY_PATTERN.sub(_ruby_to_base, html)
    s = _TAG_PATTERN.sub("", s)
    s = _INVISIBLE_PATTERN.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()
