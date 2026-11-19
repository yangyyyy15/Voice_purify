import numpy as np
import soundfile as sf

from backend.pipeline.step8_export import run


def test_export_writes_aligned_ab_segment_tracks(tmp_path, monkeypatch):
    from backend import config

    monkeypatch.setattr(config, "EXPORT_COMPENSATE", True)
    monkeypatch.setattr(config, "EXPORT_COMP_GAIN_DB", 3.0)
    monkeypatch.setattr(config, "EXPORT_COMP_FREQ_HZ", 5000)
    monkeypatch.setattr(config, "EXPORT_BOTH", True)
    monkeypatch.setattr(config, "EXPORT_PAD_MS", 80)
    monkeypatch.setattr(config, "EXPORT_FADE_MS", 15)
    sr = config.EXPORT_SAMPLE_RATE
    t = np.arange(sr, dtype=np.float32) / sr
    source = tmp_path / "vocals.wav"
    sf.write(source, 0.2 * np.sin(2 * np.pi * 440 * t), sr)

    result = run(source, tmp_path, [{"id": "seg_1", "start": 0.2, "end": 0.4, "type": "speech"},
                                    {"id": "seg_2", "start": 0.5, "end": 0.6, "type": "non_speech"}])

    files = result["segments"]["seg_1"]
    assert set(files) == {"raw", "compensated"}
    assert "seg_2" not in result["segments"]
    raw, raw_sr = sf.read(files["raw"])
    compensated, comp_sr = sf.read(files["compensated"])
    assert raw_sr == comp_sr == sr
    assert len(raw) == len(compensated) == round((0.2 + 2 * config.EXPORT_PAD_MS / 1000) * sr)
    assert abs(raw[0]) < 0.01 and abs(compensated[-1]) < 0.01
