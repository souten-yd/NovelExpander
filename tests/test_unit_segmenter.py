from speaker_split.unit_segmenter import segment_scene_units


def test_dialogue_detection_by_kagi_kakko():
    scene = {"scene_id": "scene_0001", "blocks": [{"text": "「こんにちは」"}]}
    units = segment_scene_units(scene)
    assert units[0]["pass1_label"] == "dialogue"


def test_split_mixed_paragraph():
    scene = {"scene_id": "scene_0001", "blocks": [{"text": "「こんにちは」彼は笑った。"}]}
    units = segment_scene_units(scene)
    assert len(units) == 2
    assert units[0]["pass1_label"] == "dialogue"
    assert units[1]["pass1_label"] == "narration"


def test_nonverbal_detection():
    scene = {"scene_id": "scene_0001", "blocks": [{"text": "（うなずく）"}]}
    units = segment_scene_units(scene)
    assert units[0]["pass1_label"] == "nonverbal"


def test_monologue_detection():
    scene = {"scene_id": "scene_0001", "blocks": [{"text": "（どうしてこんなことに……）"}]}
    units = segment_scene_units(scene)
    assert units[0]["pass1_label"] == "monologue"


def test_meta_detection():
    scene = {"scene_id": "scene_0001", "blocks": [{"text": "目次", "is_meta": True}]}
    units = segment_scene_units(scene)
    assert units[0]["pass1_label"] == "meta"


def test_embedded_quote_is_not_over_split():
    scene = {"scene_id": "scene_0001", "blocks": [{"text": "彼は「まずい」と言った。"}]}
    units = segment_scene_units(scene)
    assert len(units) == 1
    assert units[0]["surface_text"] == "彼は「まずい」と言った。"


def test_output_fields_and_stable_ordering():
    scene = {
        "scene_id": "scene_0002",
        "blocks": [{"text": "「A」\n\n地の文", "source_indexes": [42], "source_file": "doc.xhtml", "raw_html": "<p>「A」 地の文</p>"}],
    }
    units = segment_scene_units(scene)
    assert [u["order_in_scene"] for u in units] == [0, 1]
    assert [u["source_indexes"] for u in units] == [[42], [42]]

    required = {
        "unit_id",
        "scene_id",
        "order_in_scene",
        "source_indexes",
        "surface_text",
        "normalized_text",
        "unit_type",
        "mode",
        "speaker",
        "speaker_canonical_id",
        "speaker_candidates",
        "confidence",
        "evidence",
        "alternatives",
        "post_resolve_actions",
        "source_file",
        "raw_html",
        "prev_context",
        "next_context",
    }
    assert required.issubset(set(units[0].keys()))


def test_monologue_paragraph_is_separated_from_narration():
    scene = {"scene_id": "scene_0003", "blocks": [{"text": "（ここで諦めるわけにはいかない……）\n\n太郎は拳を握った。"}]}
    units = segment_scene_units(scene)

    assert [u["pass1_label"] for u in units] == ["monologue", "narration"]


def test_meta_paragraph_is_separated_from_body_paragraph():
    scene = {
        "scene_id": "scene_0004",
        "blocks": [{"text": "掲載情報\n\n本文", "block_type": "meta", "is_meta": True}],
    }
    units = segment_scene_units(scene)

    assert [u["pass1_label"] for u in units] == ["meta", "meta"]


def test_mixed_paragraph_splits_dialogue_and_nonverbal_and_narration():
    scene = {"scene_id": "scene_0005", "blocks": [{"text": "「わかった」（うなずく）彼は去った。"}]}
    units = segment_scene_units(scene)

    assert [u["surface_text"] for u in units] == ["「わかった」", "（うなずく）彼は去った。"]
    assert [u["pass1_label"] for u in units] == ["dialogue", "narration"]
