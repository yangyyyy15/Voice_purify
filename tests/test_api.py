"""API 测试：用合成的项目文件，不依赖模型和 ffmpeg。"""
import importlib
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_PURIFY_DATA", str(tmp_path))
    from backend import config
    importlib.reload(config)
    from backend import api
    importlib.reload(api)
    config.ensure_dirs()

    media = tmp_path / "v.mp4"
    media.write_bytes(bytes(range(256)) * 100)
    peaks = tmp_path / "peaks.json"
    peaks.write_text(json.dumps({"rate": 50, "data": [0.1, 0.5]}))
    proj = {
        "video_id": "demo_1", "source_video": str(media), "media": str(media), "peaks": str(peaks),
        "audio_analysis": "a.wav", "audio_export": "b.wav", "duration": 10.0,
        "speakers": [{"id": "SPEAKER_00", "name": "说话人1", "color": "#ff0000"}],
        "segments": [
            {"id": "seg_00001", "start": 0.5, "end": 2.0, "type": "speech", "speaker": "SPEAKER_00",
             "text": "你好", "words": [], "flags": []},
            {"id": "seg_00002", "start": 3.0, "end": 4.0, "type": "overlap", "overlap_speakers": ["SPEAKER_00"]},
        ],
    }
    (config.PROJECTS_DIR / "demo_1.json").write_text(json.dumps(proj, ensure_ascii=False), encoding="utf-8")
    return TestClient(api.app), config


def test_list_and_get(client):
    c, _ = client
    items = c.get("/api/projects").json()
    assert [i["id"] for i in items] == ["demo_1"]
    p = c.get("/api/projects/demo_1").json()
    assert p["segments"][0]["text"] == "你好"


def test_bad_id(client):
    c, _ = client
    for bad in ("..%2F..%2Fetc", "a.b", "x%5C..%5Cy"):
        assert c.get(f"/api/projects/{bad}").status_code in (400, 404)
    assert c.get("/api/projects/nope").status_code == 404
    assert c.get("/api/nothing/here").status_code == 404


def test_save_roundtrip_and_backup(client):
    c, config = client
    p = c.get("/api/projects/demo_1").json()
    p["speakers"][0]["name"] = "张三"
    p["segments"][0]["reviewed"] = True
    p["media"] = "C:/Windows/win.ini"     # 前端不能改媒体路径
    r = c.put("/api/projects/demo_1", json=p)
    assert r.status_code == 200, r.text
    saved = c.get("/api/projects/demo_1").json()
    assert saved["speakers"][0]["name"] == "张三"
    assert saved["segments"][0]["reviewed"] is True
    assert saved["media"].endswith("v.mp4")
    assert len(list((config.PROJECTS_DIR / ".history" / "demo_1").glob("*.json"))) == 1


def test_save_invalidates_stale_segment_exports(client):
    c, config = client
    path = config.PROJECTS_DIR / "demo_1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["segment_audio_exports"] = {
        "seg_00001": {"raw": "old-audio.wav"},
        "seg_00002": {"raw": "overlap.wav"},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    edited = c.get("/api/projects/demo_1").json()
    edited["segments"][0]["start"] = 0.75
    assert c.put("/api/projects/demo_1", json=edited).status_code == 200
    saved = c.get("/api/projects/demo_1").json()
    assert saved["segment_audio_exports"] == {"seg_00002": {"raw": "overlap.wav"}}

    saved["segments"] = saved["segments"][:1]
    assert c.put("/api/projects/demo_1", json=saved).status_code == 200
    assert c.get("/api/projects/demo_1").json()["segment_audio_exports"] == {}


def test_save_rejects_invalid(client):
    c, _ = client
    p = c.get("/api/projects/demo_1").json()
    bad = json.loads(json.dumps(p))
    bad["segments"][0]["end"] = 0.1
    assert c.put("/api/projects/demo_1", json=bad).status_code == 422
    bad = json.loads(json.dumps(p))
    bad["segments"][0]["speaker"] = "GHOST"
    assert c.put("/api/projects/demo_1", json=bad).status_code == 400
    bad = json.loads(json.dumps(p))
    bad["segments"][1]["id"] = "seg_00001"
    assert c.put("/api/projects/demo_1", json=bad).status_code == 400


def test_media_range(client):
    c, _ = client
    r = c.get("/api/projects/demo_1/media", headers={"Range": "bytes=10-19"})
    assert r.status_code == 206
    assert r.content == bytes(range(10, 20))
    assert r.headers["content-range"] == "bytes 10-19/25600"
    r = c.get("/api/projects/demo_1/media", headers={"Range": "bytes=-5"})
    assert r.status_code == 206 and len(r.content) == 5
    assert c.get("/api/projects/demo_1/media").status_code == 200


def test_peaks(client):
    c, _ = client
    assert c.get("/api/projects/demo_1/peaks").json()["rate"] == 50
