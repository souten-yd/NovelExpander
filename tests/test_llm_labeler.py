from speaker_split.llm_labeler import label_units_with_llm


def test_retry_three_times_then_unknown_fallback():
    calls = {"n": 0}

    def broken_llm(_payload):
        calls["n"] += 1
        return "{not-json"

    units = [{"unit_id": "u1", "pass1_label": "dialogue", "text": "「やあ」"}]
    characters = [{"id": "narrator"}, {"id": "unknown"}]
    out = label_units_with_llm(units, characters, max_retries=3, llm_call=broken_llm)

    assert calls["n"] == 3
    assert out[0]["speaker"] == "unknown"
    assert out[0]["confidence"] == 0.0


def test_retry_strategy_and_extended_output_fields():
    calls: list[dict] = []

    def flaky_llm(payload):
        calls.append(payload)
        if len(calls) < 3:
            return "{not-json"
        return (
            '{"speaker":"alice","speaker_canonical_id":"alice","confidence":0.8,'
            '"evidence":"context_match","alternatives":[{"speaker":"bob","confidence":0.1}],'
            '"unit_type":"dialogue","mode":"utterance"}'
        )

    units = [
        {
            "unit_id": "u1",
            "scene_id": "s1",
            "chapter_title": "ch1",
            "pass1_label": "dialogue",
            "unit_type": "dialogue",
            "mode": "utterance",
            "surface_text": "「やあ」",
        }
    ]
    characters = [{"id": "unknown"}, {"id": "alice"}, {"id": "bob"}]
    out = label_units_with_llm(units, characters, max_retries=3, llm_call=flaky_llm)

    assert len(calls) == 3
    # 1st and 2nd attempts are same prompt; 3rd is strict JSON.
    assert calls[0]["messages"] == calls[1]["messages"]
    assert calls[0]["response_format"] is None
    assert calls[2]["response_format"] == {"type": "json_object"}
    assert "STRICT" in calls[2]["messages"][0]["content"]
    assert out[0]["speaker"] == "alice"
    assert out[0]["speaker_canonical_id"] == "alice"
    assert out[0]["evidence"] == "context_match"
    assert out[0]["alternatives"][0]["speaker"] == "bob"
    assert out[0]["unit_type"] == "dialogue"
    assert out[0]["mode"] == "utterance"


def test_error_buckets_are_aggregated_to_run_report():
    calls = {"n": 0}

    def mixed_errors(_payload):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("timed out")
        if calls["n"] == 2:
            raise RuntimeError("rate limit exceeded")
        return "{not-json"

    units = [{"unit_id": "u1", "pass1_label": "dialogue", "surface_text": "「やあ」"}]
    characters = [{"id": "narrator"}, {"id": "unknown"}]
    report = {}
    label_units_with_llm(units, characters, max_retries=3, llm_call=mixed_errors, run_report=report)

    assert report["llm_errors"]["timeout"] == 1
    assert report["llm_errors"]["rate_limit"] == 1
    assert report["llm_errors"]["invalid_json"] == 1
