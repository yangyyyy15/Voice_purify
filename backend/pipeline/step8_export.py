"""Create aligned 48 kHz vocal tracks for export and A/B evaluation."""
from pathlib import Path

from .. import config
from .common import load_wav_mono, log, save_wav


def run(vocals_48k: Path, cache: Path, segments: list[dict]) -> dict:
    import numpy as np
    from scipy.signal import butter, sosfiltfilt

    audio, sr = load_wav_mono(vocals_48k, expected_sr=config.EXPORT_SAMPLE_RATE)
    raw_path = cache / "vocals_raw_48k.wav"
    enhanced_path = cache / "vocals_compensated_48k.wav"
    save_wav(raw_path, np.clip(audio, -1, 1), sr)

    if config.EXPORT_COMPENSATE and config.EXPORT_COMP_GAIN_DB > 0:
        cutoff = min(max(config.EXPORT_COMP_FREQ_HZ, 100), int(sr * 0.45))
        low_sos = butter(2, cutoff, btype="lowpass", fs=sr, output="sos")
        low = sosfiltfilt(low_sos, audio).astype(np.float32)
        gain = 10 ** (config.EXPORT_COMP_GAIN_DB / 20)
        enhanced = low + (audio - low) * gain
        peak = float(np.max(np.abs(enhanced))) if enhanced.size else 0.0
        if peak > 1:
            enhanced /= peak
    else:
        enhanced = audio
    save_wav(enhanced_path, np.clip(enhanced, -1, 1), sr)
    raw_segments = cache / "vocals_raw"
    comp_segments = cache / "vocals_compensated"
    segment_files = {}
    pad = round(config.EXPORT_PAD_MS * sr / 1000)
    fade = round(config.EXPORT_FADE_MS * sr / 1000)
    for segment in segments:
        if segment["type"] not in ("speech", "overlap"):
            continue
        start = max(0, round(segment["start"] * sr) - pad)
        end = min(len(audio), round(segment["end"] * sr) + pad)
        if end <= start:
            continue

        def write_segment(folder: Path, source):
            folder.mkdir(parents=True, exist_ok=True)
            piece = source[start:end].copy()
            ramp = min(fade, len(piece) // 2)
            if ramp:
                piece[:ramp] *= np.linspace(0, 1, ramp, dtype=np.float32)
                piece[-ramp:] *= np.linspace(1, 0, ramp, dtype=np.float32)
            path = folder / f"{segment['id']}.wav"
            save_wav(path, np.clip(piece, -1, 1), sr)
            return str(path)

        files = {"compensated": write_segment(comp_segments, enhanced)}
        if config.EXPORT_BOTH:
            files["raw"] = write_segment(raw_segments, audio)
        segment_files[segment["id"]] = files
    log.info("  导出人声轨：原始对照 %s；高频补偿 %s", raw_path.name, enhanced_path.name)
    return {"raw": str(raw_path), "compensated": str(enhanced_path), "segments": segment_files}
