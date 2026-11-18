import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api";
import type { ProjectSummary } from "./types";
import { fmtTime } from "./util";
import { Review } from "./Review";
import "./style.css";

function ProjectList({ onOpen }: { onOpen: (id: string) => void }) {
  const [items, setItems] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.list().then(setItems).catch((e) => setError(String(e.message ?? e))); }, []);
  return (
    <div className="pad list-page">
      <h2>Voice_purify 项目</h2>
      {error && <p className="error">无法连接后端：{error}</p>}
      {items && items.length === 0 && (
        <p className="muted">还没有项目。先运行：<code>python -m backend.pipeline.run data/input/视频.mp4</code></p>
      )}
      {items && items.length > 0 && (
        <table className="projects">
          <thead><tr><th>视频</th><th>时长</th><th>说话人</th><th>核验进度</th><th>修改时间</th></tr></thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id} onClick={() => onOpen(p.id)}>
                <td><b>{p.source}</b><div className="muted small">{p.id}</div></td>
                <td>{fmtTime(p.duration, false)}</td>
                <td>{p.speakers}</td>
                <td><progress value={p.reviewed} max={Math.max(1, p.segments)} /> {p.reviewed}/{p.segments}</td>
                <td className="small">{p.modified.replace("T", " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function App() {
  const read = () => new URLSearchParams(location.search).get("p");
  const [id, setId] = useState<string | null>(read);
  useEffect(() => {
    const h = () => setId(read());
    window.addEventListener("popstate", h);
    return () => window.removeEventListener("popstate", h);
  }, []);
  const go = (next: string | null) => {
    history.pushState(null, "", next ? `?p=${encodeURIComponent(next)}` : location.pathname);
    setId(next);
  };
  return id ? <Review key={id} id={id} onBack={() => go(null)} /> : <ProjectList onOpen={go} />;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
