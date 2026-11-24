import json
from pathlib import Path

from fieldguide.guidance import KnowledgeBase

KB_PATH = Path(__file__).resolve().parents[1] / "data" / "knowledge_base.json"


def test_shipped_knowledge_base_is_valid():
    kb = KnowledgeBase.load(KB_PATH)
    assert kb.warnings == []
    assert len(kb.entries) >= 20
    assert kb.get("cell phone") and kb.get("Laptop")        # case-insensitive
    for e in kb.entries.values():
        assert e.steps and e.tutorial_queries


def test_invalid_entries_rejected_and_duplicates_reported(tmp_path):
    p = tmp_path / "kb.json"
    p.write_text(json.dumps({"entries": [
        {"label": "a", "steps": ["do"]},
        {"label": "a", "steps": ["again"]},
        {"label": "", "steps": ["x"]},
        {"label": "nosteps", "steps": []},
        "junk",
        {"label": "v", "steps": ["s"], "curated_videos": [{"video_id": "abc", "title": "T"}, {"title": "no id"}]},
    ]}))
    kb = KnowledgeBase.load(p)
    assert set(kb.entries) == {"a", "v"}
    assert len(kb.warnings) == 4
    assert len(kb.get("v").curated_videos) == 1


def test_missing_or_broken_file_is_not_fatal(tmp_path):
    assert KnowledgeBase.load(tmp_path / "none.json").warnings
    bad = tmp_path / "bad.json"
    bad.write_text("{oops")
    assert KnowledgeBase.load(bad).warnings


def test_generic_entry_for_unknown_label():
    e = KnowledgeBase().entry_or_generic("soldering_iron")
    assert e.generic and "soldering iron" in e.summary and e.steps == []
