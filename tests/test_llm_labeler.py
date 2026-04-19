from speaker_split.llm_labeler import label_units_with_llm


def test_retry_three_times_then_unknown_fallback():
    calls = {"n": 0}

    def broken_llm(_payload):
        calls["n"] += 1
        return "{not-json"

    units = [{"unit_id": "u1", "pass1_label": "dialogue", "text": "「やあ」"}]
    characters = [{"canonical": "narrator"}, {"canonical": "unknown"}]
    out = label_units_with_llm(units, characters, max_retries=3, llm_call=broken_llm)

    assert calls["n"] == 3
    assert out[0]["speaker"] == "unknown"
    assert out[0]["confidence"] == 0.0
