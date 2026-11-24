"""YouTube tutorial lookup with SQLite caching and an offline fallback."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import TutorialConfig
from .models import Entry, Video

API_URL = "https://www.googleapis.com/youtube/v3/search"


@dataclass
class TutorialResult:
    videos: list[Video] = field(default_factory=list)
    source: str = "none"          # curated | cache | api | fallback
    query: str = ""
    search_url: str = ""
    message: str = ""


def build_query(entry: Entry) -> str:
    if entry.tutorial_queries:
        return entry.tutorial_queries[0]
    return f"how to use {entry.display_name.lower()} for beginners"


def search_page_url(query: str) -> str:
    return "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query})


def parse_search_response(data: dict, max_results: int = 5) -> list[Video]:
    videos: list[Video] = []
    for item in data.get("items", []) if isinstance(data, dict) else []:
        try:
            vid = item["id"]["videoId"]
            sn = item["snippet"]
            thumbs = sn.get("thumbnails", {})
            thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
            videos.append(Video(title=str(sn.get("title", "Untitled")), channel=str(sn.get("channelTitle", "")),
                                video_id=str(vid), thumbnail=thumb))
        except (KeyError, TypeError):
            continue
        if len(videos) >= max_results:
            break
    return videos


class TutorialCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS tutorial_cache (query TEXT PRIMARY KEY, "
                      "payload_json TEXT NOT NULL, fetched_at REAL NOT NULL)")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    def get(self, query: str, max_age_days: int) -> list[Video] | None:
        with self._conn() as c:
            row = c.execute("SELECT payload_json, fetched_at FROM tutorial_cache WHERE query=?", (query,)).fetchone()
        if row is None or time.time() - row[1] > max_age_days * 86400:
            return None
        try:
            return [Video(**v) for v in json.loads(row[0])]
        except (TypeError, json.JSONDecodeError):
            return None

    def put(self, query: str, videos: list[Video]) -> None:
        payload = json.dumps([v.__dict__ for v in videos])
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO tutorial_cache VALUES (?,?,?)", (query, payload, time.time()))


def _default_fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=6) as resp:  # noqa: S310 (fixed https URL)
        return resp.read()


class TutorialService:
    def __init__(self, cfg: TutorialConfig, cache_path: str | Path,
                 fetch: Callable[[str], bytes] | None = None) -> None:
        self.cfg = cfg
        self.cache = TutorialCache(cache_path)
        self.fetch = fetch or _default_fetch

    @property
    def api_key(self) -> str:
        return os.environ.get(self.cfg.api_key_env, "").strip()

    def find(self, entry: Entry) -> TutorialResult:
        query = build_query(entry)
        result = TutorialResult(query=query, search_url=search_page_url(query))
        curated = list(entry.curated_videos)

        cached = self.cache.get(query, self.cfg.cache_days)
        if cached is not None:
            result.videos, result.source = self._merge(curated, cached), "cache"
            return result
        if not self.api_key:
            result.videos = curated
            result.source = "curated" if curated else "fallback"
            result.message = (f"No YouTube API key found (set {self.cfg.api_key_env}). "
                              "Use the search link to see tutorials.")
            return result
        params = {"part": "snippet", "type": "video", "maxResults": self.cfg.max_results,
                  "videoEmbeddable": "true", "safeSearch": "moderate", "q": query,
                  "relevanceLanguage": self.cfg.language, "key": self.api_key}
        try:
            raw = self.fetch(API_URL + "?" + urllib.parse.urlencode(params))
            found = parse_search_response(json.loads(raw), self.cfg.max_results)
        except urllib.error.HTTPError as exc:
            result.message = ("YouTube quota or key problem (HTTP %s). Use the search link instead." % exc.code)
            result.videos, result.source = curated, "curated" if curated else "fallback"
            return result
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            result.message = "Could not reach YouTube. Use the search link when you are online."
            result.videos, result.source = curated, "curated" if curated else "fallback"
            return result
        if found:
            self.cache.put(query, found)
        else:
            result.message = "YouTube returned no videos for this search."
        result.videos = self._merge(curated, found)
        result.source = "api" if found else ("curated" if curated else "fallback")
        return result

    def _merge(self, curated: list[Video], found: list[Video]) -> list[Video]:
        seen, out = set(), []
        for v in curated + found:
            if v.video_id not in seen:
                seen.add(v.video_id)
                out.append(v)
        return out[: max(self.cfg.max_results, len(curated))]
