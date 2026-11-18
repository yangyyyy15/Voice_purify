# Voice_purify

识别视频里「谁在什么时间说了什么」，并用网页界面人工核验、调整。设计说明见 `docs/开发规程.md`。

## 安装（台式机，NVIDIA 显卡）

```bat
py -3.11 -m venv venv
venv\Scripts\activate
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r backend\requirements.txt
rem 可选：Whisper 后端
pip install faster-whisper
```

还需要：
- ffmpeg：下载后把 `bin` 目录加入 PATH。
- Hugging Face token：登录后在 `pyannote/speaker-diarization-3.1` 和 `pyannote/segmentation-3.0` 页面同意使用条款，然后 `set HF_TOKEN=hf_xxx`。
- 前端：`cd frontend && npm install && npm run build`。

检查环境：`python -m backend.check_env`

## 使用

```bat
rem 1. 识别（结果在 data\projects\<id>.json）
python -m backend.pipeline.run data\input\会议.mp4 --num-speakers 3 --hotwords "张三 李四"

rem 2. 打开核验界面 http://127.0.0.1:8000
python -m uvicorn backend.api:app --port 8000
```

常用参数：
- `--num-speakers N`：已知人数时一定要填，说话人分离会准很多。
- `--asr whisper`：中英混说多时改用 Whisper。
- `--from step5`：从某一步起重跑（其他参数改动会自动判断要重跑哪些步）。
- `--no-demucs` / `--no-events`：跳过人声分离 / 非人声检测，做对比用。

阈值等参数都在 `backend/config.py`。

重新识别同一视频会覆盖项目文件，旧文件（包括人工核验结果）会先备份成 `.bak.json`。核验界面每次保存都会在 `data/projects/.history/` 里留一份历史，最多保留 20 份。

## 不装模型试用界面

```bat
python -m tests.make_demo
python -m uvicorn backend.api:app --port 8000
```

## 测试

```bat
pip install pytest httpx
python -m pytest tests
```
