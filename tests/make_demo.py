"""
生成一个演示项目（合成音频 + 假的识别结果），不需要模型和 ffmpeg，用来试用核验 UI。
  python -m tests.make_demo
然后启动后端，浏览器打开项目 demo_synthetic。
"""
import numpy as np

from backend import config
from backend.pipeline.common import save_wav, write_json
from backend.pipeline.step1_extract import compute_peaks
from backend.pipeline.step7_merge import merge


def main():
    config.ensure_dirs()
    cache = config.CACHE_DIR / "demo_synthetic"
    sr, dur = 16000, 60.0
    rng = np.random.default_rng(0)
    t = np.arange(int(sr * dur)) / sr
    audio = 0.01 * rng.standard_normal(len(t))

    turns, words = [], []
    script = [("SPEAKER_00", 1.0, 6.0, "大家好，今天我们讨论一下新方案。"),
              ("SPEAKER_01", 6.5, 11.0, "好的，我先说一下进度。"),
              ("SPEAKER_00", 11.5, 16.0, "预算方面还有问题吗？"),
              ("SPEAKER_02", 20.0, 26.0, "我觉得时间安排有点紧张。"),
              ("SPEAKER_01", 26.5, 31.0, "可以把测试提前两天。"),
              ("SPEAKER_00", 40.0, 47.0, "那就这么定了，散会。")]
    for spk, s, e, text in script:
        f0 = {"SPEAKER_00": 130, "SPEAKER_01": 210, "SPEAKER_02": 170}[spk]
        m = (t >= s) & (t < e)
        audio[m] += 0.3 * np.sin(2 * np.pi * f0 * t[m]) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t[m]))
        turns.append({"start": s, "end": e, "speaker": spk})
        chars = [c for c in text if c not in "，。？"]
        step = (e - s) / len(chars)
        for i, c in enumerate(chars):
            nxt = text[text.index(c) + 1] if text.index(c) + 1 < len(text) else ""
            words.append({"word": c + (nxt if nxt in "，。？" else ""),
                          "start": round(s + i * step, 3), "end": round(s + (i + 0.9) * step, 3)})
    # 重叠：33~37 秒两人同时说
    m = (t >= 33) & (t < 37)
    audio[m] += 0.25 * np.sin(2 * np.pi * 130 * t[m]) + 0.25 * np.sin(2 * np.pi * 210 * t[m])
    turns += [{"start": 33.0, "end": 37.0, "speaker": "SPEAKER_00"}, {"start": 33.5, "end": 37.0, "speaker": "SPEAKER_01"}]
    # 铃声：50~54 秒
    m = (t >= 50) & (t < 54)
    audio[m] += 0.3 * np.sign(np.sin(2 * np.pi * 880 * t[m])) * (np.sin(2 * np.pi * 2 * t[m]) > 0)
    events = [{"start": 50.0, "end": 54.0, "label": "Ringtone", "score": 0.9}]

    wav = cache / "analysis_16k.wav"
    save_wav(wav, np.clip(audio, -1, 1).astype("float32"), sr)
    compute_peaks(wav, cache / "peaks.json")
    segs = merge(dur, turns, [[33.5, 37.0]], words, [[s, e] for _, s, e, _ in script], events)
    project = {
        "video_id": "demo_synthetic", "source_video": "demo_synthetic.wav", "media": str(wav.resolve()),
        "peaks": str((cache / "peaks.json").resolve()), "audio_analysis": str(wav), "audio_export": str(wav),
        "duration": dur, "created_at": "", "pipeline_params": {"demo": True},
        "speakers": [{"id": f"SPEAKER_0{i}", "name": f"说话人{i + 1}", "color": c}
                     for i, c in enumerate(["#e6194b", "#3cb44b", "#4363d8"])],
        "segments": segs,
    }
    write_json(config.PROJECTS_DIR / "demo_synthetic.json", project, indent=1)
    print(f"已生成 {len(segs)} 个片段：", config.PROJECTS_DIR / "demo_synthetic.json")


if __name__ == "__main__":
    main()
