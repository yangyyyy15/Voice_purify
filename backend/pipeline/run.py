"""
流水线主控。

用法（项目根目录执行）：
  python -m backend.pipeline.run data/input/会议.mp4
  python -m backend.pipeline.run data/input/会议.mp4 --num-speakers 3
  python -m backend.pipeline.run data/input/会议.mp4 --asr whisper --from step6
  python -m backend.pipeline.run data/input/会议.mp4 --hotwords "张三 李四 项目代号"

缓存：每步结果存在 data/cache/<id>/，manifest.json 记录各步参数指纹。
参数变化或指定 --from 时，该步及之后的步骤重跑。
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

from .. import config
from .common import log, read_json, setup_logging, write_json

STEPS = ["step1", "step2", "step3", "step4", "step5", "step6", "step7", "step8"]
PALETTE = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6",
           "#9a6324", "#469990", "#808000", "#000075", "#e6beff", "#aaffc3", "#ffd8b1"]


def make_video_id(video: Path) -> str:
    """文件名（去掉不安全字符）+ 路径哈希，同名不同路径的视频不会冲突。"""
    stem = re.sub(r"[^\w-]+", "_", video.stem).strip("_")[:40] or "video"
    h = hashlib.sha1(str(video.resolve()).lower().encode("utf-8")).hexdigest()[:6]
    return f"{stem}_{h}"


def _fingerprint(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def step_params(args, video: Path) -> dict:
    st = video.stat()
    return {
        "step1": {"video": str(video.resolve()), "size": st.st_size, "mtime": int(st.st_mtime),
                  "preview": config.MAKE_PREVIEW},
        "step2": {"demucs": config.USE_DEMUCS and not args.no_demucs, "model": config.DEMUCS_MODEL,
                  "export_track": 1},
        "step3": {"th": config.VAD_THRESHOLD, "sp": config.VAD_MIN_SPEECH_MS, "si": config.VAD_MIN_SILENCE_MS},
        "step4": {"skip": args.no_events, "th": [config.EVENT_NOISE_THRESHOLD, config.EVENT_SPEECH_THRESHOLD],
                  "labels": config.NOISE_LABELS, "win": [config.EVENT_WINDOW_S, config.EVENT_HOP_S]},
        "step5": {"pipe": config.PYANNOTE_PIPELINE, "n": args.num_speakers or config.NUM_SPEAKERS,
                  "min": config.MIN_SPEAKERS, "max": config.MAX_SPEAKERS, "th": config.CLUSTERING_THRESHOLD},
        "step6": {"backend": args.asr or config.ASR_BACKEND, "hot": args.hotwords,
                  "on_vocals": config.ASR_ON_VOCALS,
                  "model": config.FUNASR_MODEL if (args.asr or config.ASR_BACKEND) == "funasr"
                  else config.WHISPER_MODEL},
        "step7": {"gap": config.MERGE_GAP_S, "tol": config.ATTACH_TOL_S, "max": config.MAX_SEGMENT_S},
        "step8": {"use_vocals": config.EXPORT_USE_VOCALS,
                  "compensate": config.EXPORT_COMPENSATE, "gain_db": config.EXPORT_COMP_GAIN_DB,
                  "freq_hz": config.EXPORT_COMP_FREQ_HZ, "both": config.EXPORT_BOTH,
                  "pad_ms": config.EXPORT_PAD_MS, "fade_ms": config.EXPORT_FADE_MS},
    }


class Runner:
    def __init__(self, cache: Path, params: dict, force_from: str = None):
        self.cache = cache
        self.params = params
        self.manifest_path = cache / "manifest.json"
        self.manifest = read_json(self.manifest_path) if self.manifest_path.exists() else {}
        self.dirty = False   # 上游重跑过，下游必须重跑
        self.force_from = STEPS.index(force_from) if force_from else None

    def step(self, name: str, title: str, fn, out_file: str):
        out = self.cache / out_file
        fp = _fingerprint(self.params[name])
        forced = self.force_from is not None and STEPS.index(name) >= self.force_from
        if not (self.dirty or forced) and out.exists() and self.manifest.get(name) == fp:
            log.info("[%s] %s：使用缓存", name, title)
            return read_json(out)
        log.info("[%s] %s ...", name, title)
        t0 = time.time()
        result = fn()
        write_json(out, result)
        self.manifest[name] = fp
        write_json(self.manifest_path, self.manifest, indent=2)
        self.dirty = True
        log.info("[%s] 完成，用时 %.1f 秒", name, time.time() - t0)
        return result


def build_project(video_id, video, s1, analysis_audio, segments, diar, params, exports) -> dict:
    # 说话人按首次出现顺序编号配色，没出现过（只在重叠里）的也保留
    order = []
    for s in segments:
        for spk in ([s["speaker"]] if s.get("speaker") else []) + s.get("overlap_speakers", []):
            if spk not in order:
                order.append(spk)
    for spk in diar.get("labels", []):
        if spk not in order:
            order.append(spk)
    speakers = [{"id": spk, "name": f"说话人{i + 1}", "color": PALETTE[i % len(PALETTE)]}
                for i, spk in enumerate(order)]
    return {
        "schema_version": 1,
        "video_id": video_id,
        "source_video": str(video.resolve()),
        "media": s1["media"],
        "peaks": s1["peaks"],
        "audio_analysis": analysis_audio,
        "audio_export": s1["full"],
        "audio_export_raw": exports["raw"],
        "audio_export_compensated": exports["compensated"],
        "segment_audio_exports": exports["segments"],
        "duration": s1["duration"],
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "pipeline_params": params,
        "speakers": speakers,
        "segments": segments,
    }


def run_pipeline(video: Path, args) -> Path:
    from ..schema import Project
    video = video.resolve()
    if not video.exists():
        raise FileNotFoundError(video)
    config.ensure_dirs()
    video_id = args.id or make_video_id(video)
    cache = config.CACHE_DIR / video_id
    cache.mkdir(parents=True, exist_ok=True)
    params = step_params(args, video)
    runner = Runner(cache, params, args.from_step)

    device = args.device or config.get_device()
    log.info("设备: %s", device)
    if device == "cpu":
        log.warning("没有可用的 CUDA，将用 CPU 运行，长视频会很慢")

    from . import step1_extract, step2_separate, step3_vad, step4_events, step5_diarize, step6_asr
    from . import step7_merge, step8_export

    s1 = runner.step("step1", "抽取音轨", lambda: step1_extract.run(video, cache), "step1.json")

    def _sep():
        if not params["step2"]["demucs"]:
            return {"vocals": s1["analysis"]}
        return {"vocals": step2_separate.run(Path(s1["full"]), cache, device)}
    vocals = runner.step("step2", "人声分离", _sep, "step2.json")["vocals"]

    vad = runner.step("step3", "语音活动检测", lambda: step3_vad.run(Path(vocals)), "step3.json")
    events = runner.step("step4", "非人声事件检测",
                         lambda: [] if args.no_events else step4_events.run(Path(s1["full"]), cache, device),
                         "step4.json")
    diar = runner.step("step5", "说话人分离",
                       lambda: step5_diarize.run(Path(vocals), cache, device, args.num_speakers),
                       "step5.json")
    asr_audio = vocals if config.ASR_ON_VOCALS else s1["analysis"]
    asr = runner.step("step6", "语音识别",
                      lambda: step6_asr.run(Path(asr_audio), device, args.asr, args.hotwords),
                      "step6.json")
    segments = runner.step("step7", "合并时间轴",
                           lambda: step7_merge.merge(s1["duration"], diar["turns"], diar["overlaps"],
                                                     asr["words"], vad, events),
                           "step7.json")

    export_source = (Path(cache / "vocals_48k.wav")
                     if config.EXPORT_USE_VOCALS and params["step2"]["demucs"]
                     else Path(s1["full"]))
    exports = runner.step("step8", "生成人声导出轨",
                          lambda: step8_export.run(export_source, cache, segments), "step8.json")

    project = build_project(video_id, video, s1, vocals, segments, diar, params, exports)
    Project.model_validate(project)

    out = config.PROJECTS_DIR / f"{video_id}.json"
    if out.exists():
        bak = out.with_name(f"{video_id}.{dt.datetime.now():%Y%m%d_%H%M%S}.bak.json")
        shutil.copy2(out, bak)
        log.warning("已有项目文件，旧版本（含人工核验结果）已备份到 %s", bak.name)
    write_json(out, project, indent=1)

    n = {t: sum(1 for s in segments if s["type"] == t) for t in ("speech", "overlap", "non_speech")}
    log.info("完成：%s", out)
    log.info("  说话人 %d 个；片段：说话 %d，重叠 %d，非人声 %d",
             len(project["speakers"]), n["speech"], n["overlap"], n["non_speech"])
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="视频说话人识别流水线")
    p.add_argument("video", type=Path)
    p.add_argument("--id", help="项目 id，默认由文件名生成")
    p.add_argument("--num-speakers", type=int, help="已知说话人数（强烈建议填写，能提升准确率）")
    p.add_argument("--asr", choices=["funasr", "whisper"])
    p.add_argument("--hotwords", default="", help="热词，空格分隔：人名、术语")
    p.add_argument("--no-demucs", action="store_true", help="跳过人声分离")
    p.add_argument("--no-events", action="store_true", help="跳过非人声事件检测")
    p.add_argument("--from", dest="from_step", choices=STEPS, help="从某一步起强制重跑")
    p.add_argument("--device", help="cuda / cpu")
    args = p.parse_args(argv)
    setup_logging()
    try:
        run_pipeline(args.video, args)
    except Exception as e:
        log.error("%s", e)
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
