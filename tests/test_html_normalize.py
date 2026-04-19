from speaker_split.html_normalize import extract_text_fields


def test_extract_text_fields_with_ruby_in_paragraph():
    html = "<p>彼は<ruby>東京<rt>とうきょう</rt></ruby>へ行く。</p>"
    out = extract_text_fields(html)

    assert out["text"] == "彼は東京へ行く。"
    assert out["text_with_ruby"] == "彼は東京(とうきょう)へ行く。"
    assert out["ruby_map"] == [{"base": "東京", "rt": "とうきょう", "start": 2, "end": 4}]


def test_extract_text_fields_ruby_map_start_end_with_repeated_base():
    html = "<p><ruby>東京<rt>とうきょう</rt></ruby>と東京、<ruby>東京<rt>トーキョー</rt></ruby>。</p>"
    out = extract_text_fields(html)

    assert out["text"] == "東京と東京、東京。"
    assert out["text_with_ruby"] == "東京(とうきょう)と東京、東京(トーキョー)。"
    assert out["ruby_map"] == [
        {"base": "東京", "rt": "とうきょう", "start": 0, "end": 2},
        {"base": "東京", "rt": "トーキョー", "start": 3, "end": 5},
    ]


def test_extract_text_fields_normalizes_invisible_characters():
    html = "<p>彼\u200bは\u200c東\u200d京\ufeffへ\r\n行く</p>"
    out = extract_text_fields(html)

    assert out["text"] == "彼は東京へ\n行く"
    assert out["text_with_ruby"] == "彼は東京へ\n行く"
    assert out["ruby_map"] == []
