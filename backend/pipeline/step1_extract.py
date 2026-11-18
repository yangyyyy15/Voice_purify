"""
Step 1：从视频抽音轨，生成
  full_48k.wav      48kHz 单声道，导出用（保音质）
  analysis_16k.wav  16kHz 单声道原始混音，分析/波形用
  preview.mp4       （可选）浏览器无法直接播放的视频转成 480p H.264
  peaks.json        波形峰值，UI 直接画波形，不用在浏览器里解码整段音频
"""
from pathlib import Path

from .. import config
from .common import ffprobe_json, log, require_binary, run_cmd, write_json

BROWSER_VIDEO_CODECS = {"h264", "vp8", "vp9", "av1"}
BROWSER_AUDIO_CODECS = {"aac", "mp3", "opus", "vorbis", "flac", None}
PEAKS_PER_SECOND = 50


def probe_media(video: Path) -> dict:
    info = ffprobe_json(video)
    v = next((s for s in info["streams"] if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")), None)
    a = next((s for s in info["streams"] if s.get("codec_type") == "audio"), None)
    if a is None:
        raise ValueError(f"{video} 没有音轨")
    return {
        "duration": float(info["format"]["duration"]),
        "video_codec": v["codec_name"] if v else None,
        "audio_codec": a["codec_name"],
        "has_video": v is not None,
    }


def needs_preview(video: Path, meta: dict) -> bool:
    if not meta["has_video"] or config.MAKE_PREVIEW == "never":
        return False
    if config.MAKE_PREVIEW == "always":
        return True
    return (video.suffix.lower() not in config.BROWSER_FRIENDLY_EXT
            or meta["video_codec"] not in BROWSER_VIDEO_CODECS
            or meta["audio_codec"] not in BROWSER_AUDIO_CODECS)


def compute_peaks(wav_path: Path, out_path: Path):
    """每秒 PEAKS_PER_SECOND 个点的最大绝对振幅。"""
    import numpy as np
    import soundfile as sf
    peaks = []
    with sf.SoundFile(str(wav_path)) as f:
        hop = max(1, f.samplerate // PEAKS_PER_SECOND)
        for block in f.blocks(blocksize=hop * PEAKS_PER_SECOND * 60, dtype="float32", always_2d=True):
            mono = np.abs(block).max(axis=1)
            n = len(mono) // hop * hop
            if n:
                peaks.extend(mono[:n].reshape(-1, hop).max(axis=1).tolist())
            if len(mono) > n:
                peaks.append(float(mono[n:].max()))
    top = max(peaks) if peaks else 1.0
    scale = 1.0 / top if top > 0 else 1.0
    write_json(out_path, {"rate": PEAKS_PER_SECOND, "data": [round(p * scale, 3) for p in peaks]})


def run(video: Path, cache: Path) -> dict:
    ffmpeg = require_binary("ffmpeg")
    meta = probe_media(video)
    full = cache / "full_48k.wav"
    analysis = cache / "analysis_16k.wav"

    log.info("抽取音轨 (%.0f 秒)", meta["duration"])
    run_cmd([ffmpeg, "-y", "-v", "error", "-i", str(video), "-vn", "-map", "0:a:0",
             "-ac", "1", "-ar", str(config.EXPORT_SAMPLE_RATE), "-c:a", "pcm_s16le", str(full)])
    run_cmd([ffmpeg, "-y", "-v", "error", "-i", str(full),
             "-ac", "1", "-ar", str(config.ANALYSIS_SAMPLE_RATE), "-c:a", "pcm_s16le", str(analysis)])

    if needs_preview(video, meta):
        media = cache / "preview.mp4"
        log.info("视频编码 %s 浏览器可能无法播放，生成预览视频", meta["video_codec"])
        run_cmd([ffmpeg, "-y", "-v", "error", "-i", str(video), "-map", "0:v:0", "-map", "0:a:0",
                 "-vf", "scale=-2:480", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                 "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(media)])
    elif meta["has_video"]:
        media = video
    else:
        media = full  # 纯音频输入

    compute_peaks(analysis, cache / "peaks.json")
    return {
        "duration": meta["duration"],
        "full": str(full),
        "analysis": str(analysis),
        "media": str(media.resolve()),
        "peaks": str(cache / "peaks.json"),
    }
