"""
核验 UI 后端。只监听本机。

启动（项目根目录）：
  python -m uvicorn backend.api:app --port 8000
浏览器打开 http://127.0.0.1:8000
"""
import datetime as dt
import re
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config
from .pipeline.common import read_json, write_json
from .schema import Project

app = FastAPI(title="Voice_purify")
ID_RE = re.compile(r"^[\w-]{1,80}$")
MAX_BACKUPS = 20


def _project_path(pid: str) -> Path:
    if not ID_RE.match(pid):
        raise HTTPException(400, "非法项目 id")
    path = config.PROJECTS_DIR / f"{pid}.json"
    if not path.exists():
        raise HTTPException(404, "项目不存在")
    return path


def _load(pid: str) -> dict:
    return read_json(_project_path(pid))


@app.get("/api/projects")
def list_projects():
    config.ensure_dirs()
    out = []
    for p in sorted(config.PROJECTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if p.name.endswith(".bak.json") or not ID_RE.match(p.stem):
            continue
        try:
            d = read_json(p)
        except Exception:
            continue
        segs = d.get("segments", [])
        out.append({
            "id": p.stem,
            "source": Path(d.get("source_video", "")).name,
            "duration": d.get("duration", 0),
            "speakers": len(d.get("speakers", [])),
            "segments": len(segs),
            "reviewed": sum(1 for s in segs if s.get("reviewed")),
            "modified": dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
        })
    return out


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    return _load(pid)


@app.put("/api/projects/{pid}")
def save_project(pid: str, project: Project):
    path = _project_path(pid)
    if project.video_id != pid:
        raise HTTPException(400, "video_id 与路径不一致")
    # 媒体路径以服务器上的文件为准，防止前端改写成任意文件
    current = read_json(path)
    data = project.model_dump()
    for k in ("source_video", "media", "peaks", "audio_analysis", "audio_export"):
        data[k] = current[k]
    ids = [s["id"] for s in data["segments"]]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "片段 id 重复")
    spk_ids = {s["id"] for s in data["speakers"]}
    for s in data["segments"]:
        for spk in ([s["speaker"]] if s["speaker"] else []) + s["overlap_speakers"]:
            if spk not in spk_ids:
                raise HTTPException(400, f"片段 {s['id']} 引用了不存在的说话人 {spk}")
    data["segments"].sort(key=lambda s: (s["start"], s["end"]))

    bak_dir = config.PROJECTS_DIR / ".history" / pid
    bak_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, bak_dir / f"{dt.datetime.now():%Y%m%d_%H%M%S_%f}.json")
    for old in sorted(bak_dir.glob("*.json"))[:-MAX_BACKUPS]:
        old.unlink()
    write_json(path, data, indent=1)
    return {"ok": True, "saved_at": dt.datetime.now().isoformat(timespec="seconds")}


def _range_file(path: Path, request: Request, media_type: str):
    """支持 Range 请求，视频才能拖动进度条。"""
    size = path.stat().st_size
    rng = request.headers.get("range")
    if not rng:
        return FileResponse(path, media_type=media_type, headers={"Accept-Ranges": "bytes"})
    m = re.match(r"bytes=(\d*)-(\d*)", rng)
    if not m or (not m.group(1) and not m.group(2)):
        raise HTTPException(416)
    if m.group(1):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
    else:
        start, end = max(0, size - int(m.group(2))), size - 1
    end = min(end, size - 1, start + 8 * 1024 * 1024 - 1)  # 每次最多 8MB
    if start > end:
        raise HTTPException(416)
    with open(path, "rb") as f:
        f.seek(start)
        data = f.read(end - start + 1)
    return Response(data, status_code=206, media_type=media_type, headers={
        "Content-Range": f"bytes {start}-{end}/{size}", "Accept-Ranges": "bytes",
        "Content-Length": str(len(data))})


MEDIA_TYPES = {".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm",
               ".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}


@app.get("/api/projects/{pid}/media")
def get_media(pid: str, request: Request):
    path = Path(_load(pid)["media"])
    if not path.exists():
        raise HTTPException(404, f"媒体文件不存在: {path}")
    return _range_file(path, request, MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"))


@app.get("/api/projects/{pid}/peaks")
def get_peaks(pid: str):
    path = Path(_load(pid)["peaks"])
    if not path.exists():
        raise HTTPException(404, "波形数据不存在")
    return FileResponse(path, media_type="application/json")


if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        return FileResponse(config.FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def no_frontend():
        return HTMLResponse("<p>前端未构建。请在 frontend 目录执行 <code>npm install && npm run build</code>，"
                            "或开发模式 <code>npm run dev</code> 后访问 http://127.0.0.1:5173</p>")
