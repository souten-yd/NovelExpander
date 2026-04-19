from speaker_split.scene_splitter import split_scenes


def test_split_by_break_marker_and_heading():
    blocks = [
        {"text": "第一章 はじまり"},
        {"text": "本文1"},
        {"text": "※ ※ ※"},
        {"text": "本文2"},
    ]
    scenes = split_scenes(blocks)
    assert len(scenes) == 2
    assert [len(s.blocks) for s in scenes] == [2, 2]


def test_split_by_max_scene_blocks():
    blocks = [{"text": f"b{i}"} for i in range(5)]
    scenes = split_scenes(blocks, max_scene_blocks=2)
    assert len(scenes) == 3
    assert [len(s.blocks) for s in scenes] == [2, 2, 1]
