from backend.pipeline.intervals import merge_intervals, subtract_intervals
from backend.pipeline.step7_merge import merge


def W(word, s, e):
    return {"word": word, "start": s, "end": e}


def by_type(segs, t):
    return [s for s in segs if s["type"] == t]


def test_intervals():
    assert merge_intervals([(0, 1), (1.2, 2), (5, 6)], gap=0.3) == [(0, 2), (5, 6)]
    assert subtract_intervals((0, 10), [(2, 3), (5, 6)]) == [(0, 2), (3, 5), (6, 10)]
    assert subtract_intervals((0, 10), [(0, 10)]) == []


def test_basic_two_speakers():
    turns = [{"start": 0.0, "end": 2.0, "speaker": "A"}, {"start": 2.5, "end": 4.0, "speaker": "B"}]
    words = [W("你", 0.2, 0.5), W("好。", 0.5, 0.9), W("在", 2.6, 2.9), W("吗？", 2.9, 3.3)]
    segs = merge(10, turns, [], words, [[0, 4]], [])
    sp = by_type(segs, "speech")
    assert [(s["speaker"], s["text"]) for s in sp] == [("A", "你好。"), ("B", "在吗？")]
    assert [s["id"] for s in segs] == [f"seg_{i:05d}" for i in range(1, len(segs) + 1)]


def test_overlap_carved_out_and_no_text():
    turns = [{"start": 0.0, "end": 5.0, "speaker": "A"}, {"start": 3.0, "end": 8.0, "speaker": "B"}]
    words = [W("甲", 1.0, 1.3), W("吵", 3.5, 3.8), W("乙", 6.0, 6.3)]
    segs = merge(10, turns, [[3.0, 5.0]], words, [[0, 8]], [])
    ov = by_type(segs, "overlap")
    assert len(ov) == 1
    assert (ov[0]["start"], ov[0]["end"]) == (3.0, 5.0)
    assert ov[0]["text"] == "" and ov[0]["overlap_speakers"] == ["A", "B"]
    assert "吵" in ov[0]["note"]
    sp = by_type(segs, "speech")
    assert [(s["speaker"], s["start"], s["end"], s["text"]) for s in sp] == [
        ("A", 0.0, 3.0, "甲"), ("B", 5.0, 8.0, "乙")]


def test_short_overlap_ignored():
    turns = [{"start": 0.0, "end": 5.0, "speaker": "A"}, {"start": 4.9, "end": 8.0, "speaker": "B"}]
    segs = merge(10, turns, [[4.9, 5.0]], [W("一", 1, 1.2), W("二", 6, 6.2)], [], [])
    assert not by_type(segs, "overlap")


def test_word_attached_to_nearest_region():
    turns = [{"start": 1.0, "end": 2.0, "speaker": "A"}]
    segs = merge(10, turns, [], [W("嗯", 0.6, 0.9), W("好", 1.2, 1.5)], [], [])
    sp = by_type(segs, "speech")
    assert len(sp) == 1 and sp[0]["text"] == "嗯好"
    assert sp[0]["start"] == 0.6  # 片段边界扩展到包住字


def test_orphan_words_become_no_speaker():
    turns = [{"start": 0.0, "end": 1.0, "speaker": "A"}]
    segs = merge(10, turns, [], [W("一", 0.2, 0.5), W("远", 5.0, 5.3), W("处", 5.3, 5.6)], [], [])
    sp = by_type(segs, "speech")
    orphan = [s for s in sp if s["speaker"] is None]
    assert len(orphan) == 1 and orphan[0]["text"] == "远处" and "no_speaker" in orphan[0]["flags"]


def test_empty_region_over_noise_becomes_non_speech():
    turns = [{"start": 0.0, "end": 3.0, "speaker": "A"}]
    events = [{"start": 0.0, "end": 3.0, "label": "Ringtone", "score": 0.8}]
    segs = merge(10, turns, [], [], [], events)
    assert len(segs) == 1 and segs[0]["type"] == "non_speech" and segs[0]["note"] == "Ringtone"


def test_empty_region_without_noise_flagged():
    turns = [{"start": 0.0, "end": 3.0, "speaker": "A"}]
    segs = merge(10, turns, [], [], [], [])
    assert segs[0]["type"] == "speech" and "no_text" in segs[0]["flags"]


def test_noise_in_gap():
    turns = [{"start": 0.0, "end": 1.0, "speaker": "A"}]
    events = [{"start": 4.0, "end": 6.0, "label": "Music", "score": 0.9}]
    segs = merge(10, turns, [], [W("一", 0.2, 0.5)], [], events)
    ns = by_type(segs, "non_speech")
    assert [(s["start"], s["end"], s["note"]) for s in ns] == [(4.0, 6.0, "Music")]


def test_long_region_split_at_sentence_end():
    turns = [{"start": 0.0, "end": 40.0, "speaker": "A"}]
    words = []
    t = 0.0
    for i in range(70):
        tok = "字。" if i % 10 == 9 else "字"
        words.append(W(tok, t, t + 0.5))
        t += 0.55
    segs = merge(60, turns, [], words, [[0, 40]], [])
    sp = by_type(segs, "speech")
    assert len(sp) >= 2
    assert all(s["text"].endswith("。") for s in sp[:-1])
    for a, b in zip(sp, sp[1:]):
        assert a["end"] <= b["start"] + 1e-6
    assert sum(len(s["words"]) for s in sp) == 70


def test_split_on_long_silence():
    turns = [{"start": 0.0, "end": 10.0, "speaker": "A"}]
    segs = merge(10, turns, [], [W("前", 0.5, 0.8), W("后", 8.0, 8.3)], [], [])
    sp = by_type(segs, "speech")
    assert [s["text"] for s in sp] == ["前", "后"]


def test_clamped_to_duration():
    turns = [{"start": 0.0, "end": 12.0, "speaker": "A"}]
    segs = merge(10, turns, [], [W("一", 1, 1.2)], [], [])
    assert segs[-1]["end"] == 10
