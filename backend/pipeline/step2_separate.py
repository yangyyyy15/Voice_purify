"""
Step 2：Demucs 人声分离。输入 48k 原轨，输出 vocals_16k.wav（16kHz 单声道人声轨）。

长音频分块处理（每块带前后上下文，拼接时裁掉上下文），内存占用和视频时长无关。
"""
from pathlib import Path

from .. import config
from .common import load_wav_mono, log, save_wav

CHUNK_S = 600      # 每块 10 分钟
CONTEXT_S = 5      # 每块前后多算 5 秒，拼接处无接缝


def run(full_48k: Path, cache: Path, device: str) -> str:
    import numpy as np
    import torch
    from demucs.apply import apply_model
    from demucs.audio import convert_audio
    from demucs.pretrained import get_model

    out = cache / "vocals_16k.wav"
    model = get_model(config.DEMUCS_MODEL)
    model.eval()
    vocals_idx = model.sources.index("vocals")

    audio, sr = load_wav_mono(full_48k)
    total = len(audio)
    chunk, ctx = CHUNK_S * sr, CONTEXT_S * sr
    pieces = []
    for start in range(0, total, chunk):
        end = min(start + chunk, total)
        a, b = max(0, start - ctx), min(total, end + ctx)
        log.info("  Demucs %d/%d", start // chunk + 1, (total + chunk - 1) // chunk)
        wav = torch.from_numpy(audio[a:b])[None]                       # (1, n)
        wav = convert_audio(wav, sr, model.samplerate, model.audio_channels)
        ref = wav.mean(0)
        mean, std = ref.mean(), ref.std() + 1e-8
        with torch.no_grad():
            sources = apply_model(model, ((wav - mean) / std)[None], device=device,
                                  split=True, overlap=0.25, segment=config.DEMUCS_SEGMENT,
                                  progress=False)[0]
        vocals = sources[vocals_idx] * std + mean                       # (ch, n')
        vocals = convert_audio(vocals.cpu(), model.samplerate, config.ANALYSIS_SAMPLE_RATE, 1)[0].numpy()
        # 裁掉上下文（按 16k 采样点换算）
        k = config.ANALYSIS_SAMPLE_RATE / sr
        lo = round((start - a) * k)
        hi = lo + round((end - start) * k)
        pieces.append(vocals[lo:hi])
        if device.startswith("cuda"):
            torch.cuda.empty_cache()

    save_wav(out, np.clip(np.concatenate(pieces), -1, 1), config.ANALYSIS_SAMPLE_RATE)
    return str(out)
