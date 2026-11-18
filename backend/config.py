"""
全局配置：路径、模型、参数。
所有参数集中在这里，评测调参时只改这个文件（或用环境变量覆盖路径）。
"""
import os
from pathlib import Path

# Hugging Face 镜像（国内网络）。必须在导入 huggingface_hub/pyannote 之前写入环境变量才生效
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
HF_TOKEN = os.getenv("HF_TOKEN")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("VOICE_PURIFY_DATA", PROJECT_ROOT / "data"))
INPUT_DIR = DATA_DIR / "input"
CACHE_DIR = DATA_DIR / "cache"
PROJECTS_DIR = DATA_DIR / "projects"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


def ensure_dirs():
    for d in (INPUT_DIR, CACHE_DIR, PROJECTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def get_device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


# ---------- Step 1: 抽音 ----------
EXPORT_SAMPLE_RATE = 48000
ANALYSIS_SAMPLE_RATE = 16000
# 浏览器不一定能播放的格式（mkv/avi/HEVC 等）生成 480p H.264 预览视频。"auto" | "always" | "never"
MAKE_PREVIEW = "auto"
BROWSER_FRIENDLY_EXT = {".mp4", ".webm", ".m4v"}

# ---------- Step 2: 人声分离 ----------
USE_DEMUCS = True            # 关掉可做 A/B 对比
DEMUCS_MODEL = "htdemucs"
DEMUCS_SEGMENT = None        # 显存不够时设成整数秒，如 7

# ---------- Step 3: VAD ----------
VAD_THRESHOLD = 0.5
VAD_MIN_SPEECH_MS = 250
VAD_MIN_SILENCE_MS = 300

# ---------- Step 4: 非人声过滤 (PANNs, AudioSet 类别名) ----------
EVENT_WINDOW_S = 1.0
EVENT_HOP_S = 0.5
EVENT_NOISE_THRESHOLD = 0.3   # 噪音类得分高于它……
EVENT_SPEECH_THRESHOLD = 0.3  # ……且语音类得分低于它，才判为非人声（防止误杀说话）
SPEECH_LABELS = [
    "Speech", "Male speech, man speaking", "Female speech, woman speaking",
    "Child speech, kid speaking", "Conversation", "Narration, monologue",
    "Whispering", "Babbling",
]
NOISE_LABELS = [
    "Music", "Ringtone", "Telephone", "Telephone bell ringing", "Alarm",
    "Alarm clock", "Laughter", "Applause", "Clapping", "Cough", "Sneeze",
    "Siren", "Dog", "Bark", "Door", "Knock", "Typing", "Computer keyboard",
    "Beep, bleep", "Vehicle", "Car", "Engine", "Television", "Radio",
]

# ---------- Step 5: 说话人分离 (pyannote) ----------
PYANNOTE_PIPELINE = "pyannote/speaker-diarization-3.1"
# 已知人数时填上，能明显提升准确率；不知道就保持 None
NUM_SPEAKERS = None
MIN_SPEAKERS = None
MAX_SPEAKERS = None
# 聚类阈值：None 用模型默认值（约 0.70）。调高 → 说话人变少（相近声音被合并）
CLUSTERING_THRESHOLD = None

# ---------- Step 6: ASR ----------
ASR_BACKEND = "funasr"        # "funasr" | "whisper"
FUNASR_MODEL = "paraformer-zh"
FUNASR_VAD_MODEL = "fsmn-vad"
FUNASR_PUNC_MODEL = "ct-punc"
FUNASR_BATCH_SIZE_S = 300
WHISPER_MODEL = "large-v3"
# ASR 用哪条音轨：人声轨更干净，但 Demucs 偶尔损伤人声，评测时两种都试
ASR_ON_VOCALS = True

# ---------- Step 7: 合并 ----------
MERGE_GAP_S = 0.3        # 同一说话人相邻片段间隔小于它就合并
ATTACH_TOL_S = 0.5       # 字不在任何说话人区间内时，允许吸附到多远的区间
MAX_SEGMENT_S = 20.0     # 超过这个时长的片段在句末标点处拆开
SHORT_SEGMENT_S = 0.4    # 短于它的片段标 short
LOW_VAD_RATIO = 0.3      # 片段内 VAD 覆盖率低于它标 low_vad（可能是误检）
