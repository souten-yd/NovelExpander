from speaker_split.candidate_builder import (
    build_characters,
    extract_calling_mentions,
    extract_case_particle_mentions,
)


def test_extract_case_particle_mentions():
    text = "太郎は笑って、花子が頷き、店員に聞く"
    mentions = extract_case_particle_mentions(text)
    assert "太郎" in mentions
    assert "花子" in mentions
    assert "店員" in mentions


def test_extract_calling_mentions():
    text = "太郎さん、兄ちゃん、お姉ちゃん"
    mentions = extract_calling_mentions(text)
    assert "太郎" in mentions
    assert "兄" in mentions
    assert "お姉" in mentions


def test_build_characters_schema_and_scene_local_unknown_ids():
    units = [
        {
            "scene_id": "s1",
            "surface_text": "太郎は店員に言った。",
            "prev_context": "兄ちゃん、ちょっと",
            "next_context": "",
            "speaker": "unknown",
        }
    ]
    characters = build_characters(units)
    ids = {c["id"] for c in characters}
    assert "narrator" in ids
    assert "unknown" in ids
    assert "太郎".lower() in ids
    assert any(i.startswith("shopkeeper_") or i.startswith("mob_male_") for i in ids)
    assert all(set(c.keys()) == {"id", "display_name", "aliases"} for c in characters)
