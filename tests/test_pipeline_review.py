from backend.pipeline.run import preserve_reviewed_content


def test_preserves_reviewed_segment_fields_and_speaker_labels():
    regenerated = {
        "speakers": [{"id": "SPEAKER_00", "name": "说话人1", "color": "#000"}],
        "segments": [{"id": "seg_1", "start": 1.0, "end": 2.0, "type": "speech",
                      "speaker": "SPEAKER_00", "overlap_speakers": [], "text": "自动文本",
                      "words": [], "confidence": 0.8, "note": "", "flags": [], "reviewed": False},
                     {"id": "seg_2", "start": 2.0, "end": 3.0, "type": "speech",
                      "speaker": "SPEAKER_00", "overlap_speakers": [], "text": "新片段",
                      "words": [], "confidence": 0.8, "note": "", "flags": [], "reviewed": False}],
        "segment_audio_exports": {"seg_1": {"raw": "regenerated.wav"}},
    }
    previous = {
        "speakers": [{"id": "SPEAKER_00", "name": "张三", "color": "#123"}],
        "segments": [{"id": "seg_1", "start": 1.1, "end": 2.1, "type": "speech",
                      "speaker": "SPEAKER_00", "overlap_speakers": [], "text": "人工修订",
                      "words": [], "confidence": 0.8, "note": "", "flags": [], "reviewed": True}],
        "segment_audio_exports": {"seg_1": {"raw": "stale.wav"}},
    }

    result = preserve_reviewed_content(regenerated, previous)

    assert result["segments"][0]["text"] == "人工修订"
    assert result["segments"][0]["start"] == 1.1
    assert result["segments"][0]["reviewed"] is True
    assert result["segments"][1]["text"] == "新片段"
    assert result["speakers"][0]["name"] == "张三"
    assert result["speakers"][0]["color"] == "#123"
    assert result["segment_audio_exports"] == {}
