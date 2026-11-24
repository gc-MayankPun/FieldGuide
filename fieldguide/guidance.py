"""Local knowledge base: what to tell the user about each recognised object."""
from __future__ import annotations

import json
from pathlib import Path

from .models import Entry, Video


class KnowledgeBase:
    def __init__(self, entries: dict[str, Entry] | None = None) -> None:
        self.entries = entries or {}
        self.warnings: list[str] = []

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeBase":
        kb = cls()
        p = Path(path)
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            kb.warnings.append(f"Knowledge base not found: {p}. Only generic guidance will be shown.")
            return kb
        except (json.JSONDecodeError, OSError) as exc:
            kb.warnings.append(f"Could not read knowledge base {p.name}: {exc}.")
            return kb
        items = raw.get("entries", raw) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            kb.warnings.append("Knowledge base must be a list of entries.")
            return kb
        for n, item in enumerate(items, 1):
            entry = kb._parse(item, n)
            if entry is None:
                continue
            if entry.label in kb.entries:
                kb.warnings.append(f"Entry {n}: duplicate label '{entry.label}' ignored.")
                continue
            kb.entries[entry.label] = entry
        return kb

    def _parse(self, item, n: int) -> Entry | None:
        if not isinstance(item, dict):
            self.warnings.append(f"Entry {n}: not an object, skipped.")
            return None
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            self.warnings.append(f"Entry {n}: missing 'label', skipped.")
            return None
        steps = item.get("steps")
        if not isinstance(steps, list) or not steps or not all(isinstance(s, str) and s.strip() for s in steps):
            self.warnings.append(f"Entry '{label}': needs at least one step, skipped.")
            return None

        def strings(key: str) -> list[str]:
            v = item.get(key, [])
            return [s for s in v if isinstance(s, str) and s.strip()] if isinstance(v, list) else []

        videos = []
        for v in item.get("curated_videos", []) if isinstance(item.get("curated_videos", []), list) else []:
            if isinstance(v, dict) and isinstance(v.get("video_id"), str) and v["video_id"].strip():
                videos.append(Video(title=str(v.get("title", "Tutorial video")),
                                    channel=str(v.get("channel", "")), video_id=v["video_id"].strip(),
                                    curated=True))
        label = label.strip().lower()
        return Entry(label=label, display_name=str(item.get("display_name") or label.title()),
                     category=str(item.get("category", "general")), summary=str(item.get("summary", "")),
                     steps=[s.strip() for s in steps], cautions=strings("cautions"),
                     tutorial_queries=strings("tutorial_queries"), curated_videos=videos)

    def get(self, label: str) -> Entry | None:
        return self.entries.get(label.strip().lower())

    def entry_or_generic(self, label: str) -> Entry:
        found = self.get(label)
        if found is not None:
            return found
        name = label.replace("_", " ").title()
        return Entry(label=label.lower(), display_name=name,
                     summary=f"No step-by-step guide is available yet for {label.replace('_', ' ')}.",
                     generic=True)
