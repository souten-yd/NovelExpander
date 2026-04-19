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
