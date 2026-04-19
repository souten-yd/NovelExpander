from speaker_split.html_normalize import extract_text_fields


def test_extract_text_fields_with_ruby_in_paragraph():
    html = "<p>彼は<ruby>東京<rt>とうきょう</rt></ruby>へ行く。</p>"
    out = extract_text_fields(html)

    assert out["text"] == "彼は東京へ行く。"
    assert out["text_with_ruby"] == "彼は東京(とうきょう)へ行く。"
    assert out["ruby_map"] == [{"base": "東京", "rt": "とうきょう", "start": 2, "end": 4}]
