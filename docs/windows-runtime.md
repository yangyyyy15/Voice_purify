# Windows 本机环境与恢复

记录日期：2026-11-19。项目位于 `E:\Voice_purify`，基础解释器为
`D:\Python\Python311\python.exe`（3.11.9），实际运行解释器为
`E:\Voice_purify\.venv\Scripts\python.exe`。独立 venv 不继承基础环境的包，
也不修改 ComfyUI Python。原始视频、模型权重、token、venv、前端构建产物不提交。

## 重建依赖

从项目根目录在 PowerShell 执行。`requirements-runtime.txt` 是此次实际安装版本快照，
仅记录包版本，不包含登录凭据。CUDA wheel 单独从 PyTorch 官方源安装。

```powershell
& D:\Python\Python311\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.7.0 torchaudio==2.7.0 --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-runtime.txt --extra-index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m backend.setup_panns
```

关键版本：PyTorch/torchaudio 2.7.0+cu128、pyannote.audio 3.4.0、
huggingface-hub 0.24.7、transformers 4.45.2、onnxruntime-gpu 1.32.0。
不要无约束升级 Hub/Transformers：pyannote 3.x 仍使用 `use_auth_token` API。
Hugging Face token 可用 `HF_TOKEN` 或本机 CLI 缓存；0.24.7 对应 CLI 为
`.venv\Scripts\huggingface-cli.exe login`。需分别接受 diarization-3.1 和 segmentation-3.0 条款。

FFmpeg/ffprobe 不在本机系统 PATH 中。当前只在运行进程设置：

```powershell
$env:Path = 'E:\AI-T8-video-onekey-V21\ffmpeg\bin;' + $env:Path
$env:PYTHONIOENCODING = 'utf-8'
$env:HF_ENDPOINT = 'https://huggingface.co'
```

上面的 FFmpeg 路径可换成独立安装位置；只是调用二进制，不改变 ComfyUI 环境。

## 模型资源

- 默认 embedding 仓库 `pyannote/wespeaker-voxceleb-resnet34-LM` 是 **PyTorch** 格式，正常情况下并不需要 ONNX。
- 本机下载失败后选用了 `hbredin/wespeaker-voxceleb-resnet34-LM` 的 ONNX 替代文件，保存为
  `models/wespeaker-voxceleb-resnet34-LM/speaker-embedding.onnx`（26,530,309 bytes）。
  代码仅在该文件存在时使用本地替代。未证明替代模型与默认模型在本素材上的准确率相同。
- pyannote 配置与 segmentation 缓存当前位于 `%USERPROFILE%\.cache\torch\pyannote`。
- FunASR/ModelScope 模型缓存当前位于 `%USERPROFILE%\.cache\modelscope`。
- PANNs 文件放在 `models/panns/`：`class_labels_indices.csv` 与 `Cnn14_mAP=0.431.pth`。
  PANNs 0.1.1 默认依赖 wget 且将标签存入用户目录，所以需要运行 `backend.setup_panns`。
  此脚本仅补丁当前解释器所属的包，让其识别项目代码设置的 `PANNS_DATA_DIR`；重复执行安全。

PANNs 原始资源：

- https://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv
- https://zenodo.org/records/3987831/files/Cnn14_mAP%3D0.431.pth?download=1

此次实际权重 327,428,481 bytes，MD5 `541141fa2ee191a88f24a3219fff024e`，
与 Zenodo 官方记录一致。下载后核对文件，不能只凭文件名判断完整。

## 界面与已保存结果

```powershell
Push-Location frontend
npm ci
npm run build
Pop-Location
.\Start-Review.ps1
```

当前本机入口：http://127.0.0.1:8000/?p=cd24ba5b_first10min
若端口被占用，使用 `Start-Review.ps1 -Port 8001`。页面不是公网服务。
关闭程序或重启电脑后需要重新启动。界面源码在 `frontend/src`，构建结果可重新生成。

识别归档在 `runs/cd24ba5b_first10min/`，包含可编辑 project.json、波形、文本、SRT、统计与截图。
本机正在使用的核验项目仍在 `data/projects/cd24ba5b_first10min.json`；归档不会替代或覆盖它。
更换机器或目录后，用自己的前十分钟媒体副本恢复归档：

```powershell
.\.venv\Scripts\python.exe -m backend.restore_run runs\cd24ba5b_first10min --media "E:\Voice_purify\data\input\cd24ba5b_first10min.mp4"
```

恢复脚本拒绝覆盖已有核验项目。仓库不包含视频或分析音轨；缺少媒体时仍可阅读文本和截图。

## 验收范围

本素材已完成 step1 到 step7，26 项单测通过（含归档恢复与防覆盖测试），前端构建通过。
归档时另取 15 秒素材通过 CUDA 说话人分离加载与推理检查。环境检查脚本只做依赖导入/GPU/token 检查，
不能单凭它宣称所有模型加载通过或识别准确率达标。实际十分钟运行结果才是本次功能验收依据。
全部 167 段仍是未核验状态，没有人工 ground truth，因此尚未计算 DER/CER。
片头歌声被部分误识别为对话，8 个聚类标签不代表已确认 8 位人物。
ONNX Runtime 实际运行出现卷积 fallback 性能警告，但这次运行成功；尚未做性能基准。
