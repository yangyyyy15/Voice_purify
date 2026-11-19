"""
Step 4：音频事件检测（PANNs Cnn14，AudioSet 527 类）。
在原始混音上滑窗分类，找出「噪音类得分高、语音类得分低」的窗口，作为非人声区间。

用原始混音而不是人声轨：铃声、音乐等在人声轨里已被削弱，混音里才最容易认出来；
step7 用这些区间把「说话人分离误当成语音、但 ASR 没识别出字」的片段改判为非人声。
"""
from pathlib import Path
from typing import List

from .. import config
from .common import load_wav_mono, log, require_binary, run_cmd

PANNS_SR = 32000
BATCH = 64


def run(full_48k: Path, cache: Path, device: str) -> List[dict]:
    import os
    import numpy as np
    model_dir = config.PROJECT_ROOT / "models" / "panns"
    for filename in ("class_labels_indices.csv", "Cnn14_mAP=0.431.pth"):
        if not (model_dir / filename).is_file():
            raise FileNotFoundError(f"Missing PANNs asset: {model_dir / filename}. See docs/windows-runtime.md")
    os.environ["PANNS_DATA_DIR"] = str(model_dir)
    from panns_inference import AudioTagging, labels

    mix32 = cache / "mix_32k.wav"
    run_cmd([require_binary("ffmpeg"), "-y", "-v", "error", "-i", str(full_48k),
             "-ac", "1", "-ar", str(PANNS_SR), "-c:a", "pcm_s16le", str(mix32)])
    audio, sr = load_wav_mono(mix32, expected_sr=PANNS_SR)

    name_to_idx = {n: i for i, n in enumerate(labels)}
    missing = [n for n in config.SPEECH_LABELS + config.NOISE_LABELS if n not in name_to_idx]
    if missing:
        log.warning("这些类别名在 PANNs 标签里不存在，已忽略: %s", missing)
    speech_idx = [name_to_idx[n] for n in config.SPEECH_LABELS if n in name_to_idx]
    noise_names = [n for n in config.NOISE_LABELS if n in name_to_idx]
    noise_idx = [name_to_idx[n] for n in noise_names]

    win, hop = int(config.EVENT_WINDOW_S * sr), int(config.EVENT_HOP_S * sr)
    starts = list(range(0, max(1, len(audio) - win + 1), hop))
    at = AudioTagging(checkpoint_path=str(model_dir / "Cnn14_mAP=0.431.pth"), device=device)

    events = []
    for b in range(0, len(starts), BATCH):
        batch_starts = starts[b:b + BATCH]
        batch = np.stack([np.pad(audio[s:s + win], (0, max(0, win - len(audio[s:s + win]))))
                          for s in batch_starts])
        clipwise, _ = at.inference(batch)
        for s, scores in zip(batch_starts, clipwise):
            speech = float(scores[speech_idx].max()) if speech_idx else 0.0
            j = int(np.argmax(scores[noise_idx]))
            noise = float(scores[noise_idx][j])
            if noise >= config.EVENT_NOISE_THRESHOLD and speech < config.EVENT_SPEECH_THRESHOLD:
                events.append({"start": s / sr, "end": min(len(audio), s + win) / sr,
                               "label": noise_names[j], "score": round(noise, 3)})
    mix32.unlink(missing_ok=True)
    return events
