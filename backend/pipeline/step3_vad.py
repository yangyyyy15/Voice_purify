"""
Step 3：Silero VAD，在人声轨上找出有人声的区间。
输出用于：给 step4 圈定要分类的范围；step7 标记可疑片段（low_vad）。
"""
from pathlib import Path
from typing import List

from .. import config
from .common import load_wav_mono


def run(vocals_16k: Path) -> List[List[float]]:
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    model = load_silero_vad()
    audio, sr = load_wav_mono(vocals_16k, expected_sr=16000)
    ts = get_speech_timestamps(
        torch.from_numpy(audio), model,
        threshold=config.VAD_THRESHOLD,
        sampling_rate=sr,
        min_speech_duration_ms=config.VAD_MIN_SPEECH_MS,
        min_silence_duration_ms=config.VAD_MIN_SILENCE_MS,
    )
    return [[t["start"] / sr, t["end"] / sr] for t in ts]
