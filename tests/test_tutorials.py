import json
import urllib.error

from fieldguide.config import TutorialConfig
from fieldguide.models import Entry, Video
from fieldguide.tutorials import TutorialService, build_query, parse_search_response, search_page_url

API_JSON = json.dumps({"items": [
    {"id": {"videoId": "v1"}, "snippet": {"title": "One", "channelTitle": "Ch", "thumbnails": {"medium": {"url": "http://t/1.jpg"}}}},
    {"id": {"videoId": "v2"}, "snippet": {"title": "Two", "channelTitle": "Ch"}},
    {"id": {}, "snippet": {}},   # malformed, skipped
]}).encode()
ENTRY = Entry("laptop", "Laptop", steps=["x"], tutorial_queries=["how to use a laptop"])


def svc(tmp_path, fetch, key="KEY", monkeypatch=None):
    if monkeypatch is not None:
        if key:
            monkeypatch.setenv("YOUTUBE_API_KEY", key)
        else:
            monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    return TutorialService(TutorialConfig(), tmp_path / "c.db", fetch=fetch)


def test_query_and_search_url():
    assert build_query(ENTRY) == "how to use a laptop"
    assert build_query(Entry("x", "Soldering Iron")) == "how to use soldering iron for beginners"
    assert "search_query=how+to+use" in search_page_url("how to use a laptop")


def test_parse_skips_malformed():
    vids = parse_search_response(json.loads(API_JSON))
    assert [v.video_id for v in vids] == ["v1", "v2"]
    assert vids[0].url.endswith("v1") and vids[0].thumbnail


def test_api_then_cache(tmp_path, monkeypatch):
    calls = []
    s = svc(tmp_path, lambda url: calls.append(url) or API_JSON, monkeypatch=monkeypatch)
    r1 = s.find(ENTRY)
    r2 = s.find(ENTRY)
    assert r1.source == "api" and r2.source == "cache"
    assert len(calls) == 1 and "key=KEY" in calls[0]
    assert [v.video_id for v in r2.videos] == ["v1", "v2"]


def test_curated_videos_come_first(tmp_path, monkeypatch):
    e = Entry("laptop", "Laptop", steps=["x"], curated_videos=[Video("Best", "Me", "cur1", curated=True)])
    r = svc(tmp_path, lambda u: API_JSON, monkeypatch=monkeypatch).find(e)
    assert r.videos[0].video_id == "cur1" and len(r.videos) == 3


def test_no_key_gives_fallback_link(tmp_path, monkeypatch):
    r = svc(tmp_path, lambda u: 1 / 0, key="", monkeypatch=monkeypatch).find(ENTRY)
    assert r.source == "fallback" and r.search_url and "API key" in r.message


def test_network_and_quota_errors_fall_back(tmp_path, monkeypatch):
    def offline(url):
        raise urllib.error.URLError("down")

    def quota(url):
        raise urllib.error.HTTPError(url, 403, "quota", None, None)

    assert svc(tmp_path, offline, monkeypatch=monkeypatch).find(ENTRY).source == "fallback"
    r = svc(tmp_path / "b", quota, monkeypatch=monkeypatch).find(ENTRY)
    assert r.source == "fallback" and "403" in r.message


def test_key_never_appears_in_messages(tmp_path, monkeypatch):
    def boom(url):
        raise urllib.error.URLError("failed " + url)
    r = svc(tmp_path, boom, key="SECRETKEY", monkeypatch=monkeypatch).find(ENTRY)
    assert "SECRETKEY" not in r.message and "SECRETKEY" not in r.search_url


def test_expired_cache_is_refetched(tmp_path, monkeypatch):
    calls = []
    s = svc(tmp_path, lambda u: calls.append(u) or API_JSON, monkeypatch=monkeypatch)
    s.find(ENTRY)
    s.cfg.cache_days = 0
    s.find(ENTRY)
    assert len(calls) == 2
