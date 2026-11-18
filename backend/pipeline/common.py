"""
流水线公共工具：ffmpeg 调用、音频读写、JSON 读写、日志。
重型依赖（torch、soundfile 等）都在函数内部导入，保证纯逻辑模块和测试可以脱离模型环境运行。
"""
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger("voice_purify")


def setup_logging(level=logging.INFO):
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"找不到 {name}，请安装 ffmpeg 并把 bin 目录加入 PATH")
    return path


def run_cmd(args: list) -> subprocess.CompletedProcess:
    """运行外部命令（参数列表形式，不经过 shell，路径含空格/中文也安全）。失败时带上 stderr 报错。"""
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"命令失败: {' '.join(map(str, args))}\n{proc.stderr[-2000:]}")
    return proc


def ffprobe_json(path: Path) -> dict:
    proc = run_cmd([require_binary("ffprobe"), "-v", "error", "-print_format", "json",
                    "-show_format", "-show_streams", str(path)])
    return json.loads(proc.stdout)


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any, indent=None):
    """原子写入：先写临时文件再替换，避免中途崩溃留下半个文件。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, path)


def load_wav_mono(path: Path, expected_sr: int = None):
    """读 wav 为 float32 单声道 numpy 数组。"""
    import numpy as np
    import soundfile as sf
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    audio = audio.mean(axis=1) if audio.shape[1] > 1 else audio[:, 0]
    if expected_sr and sr != expected_sr:
        raise ValueError(f"{path} 采样率是 {sr}，期望 {expected_sr}")
    return np.ascontiguousarray(audio), sr


def save_wav(path: Path, audio, sr: int):
    import soundfile as sf
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".tmp.wav")
    sf.write(str(tmp), audio, sr, subtype="PCM_16")
    os.replace(tmp, path)
