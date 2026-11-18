import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { api } from "./api";
import { editReducer, initialEdit, newSpeakerId } from "./editing";
import type { Segment } from "./types";
import { fmtTime, uid } from "./util";
import { Timeline } from "./components/Timeline";
import { SpeakerPanel } from "./components/SpeakerPanel";
import { SegmentList } from "./components/SegmentList";
import { SegmentEditor } from "./components/SegmentEditor";

type Filter = "all" | "unreviewed" | "flagged" | "overlap" | "non_speech";

export function Review({ id, onBack }: { id: string; onBack: () => void }) {
  const [st, dispatch] = useReducer(editReducer, initialEdit);
  const [peaks, setPeaks] = useState<{ rate: number; data: number[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loop, setLoop] = useState(false);
  const [rate, setRate] = useState(1);
  const [filter, setFilter] = useState<Filter>("all");
  const [spkFilter, setSpkFilter] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const video = useRef<HTMLVideoElement>(null);
  const stopAt = useRef<number | null>(null);

  const p = st.project;

  useEffect(() => {
    api.get(id).then((proj) => dispatch({ type: "load", project: proj })).catch((e) => setError(String(e.message ?? e)));
    api.peaks(id).then(setPeaks).catch(() => setPeaks(null));
  }, [id]);

  // 未保存时离开页面提醒
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => { if (st.dirty) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [st.dirty]);

  const seg = p?.segments.find((s) => s.id === selectedId) ?? null;
  const segRef = useRef<Segment | null>(null);
  segRef.current = seg;
  const loopRef = useRef(loop);
  loopRef.current = loop;

  // 播放头所在的片段（优先 speech）
  const activeId = useMemo(() => {
    if (!p) return null;
    const hits = p.segments.filter((s) => time >= s.start && time < s.end);
    return (hits.find((s) => s.type === "speech") ?? hits[0])?.id ?? null;
  }, [p, time]);

  // 用 requestAnimationFrame 读播放进度，比 timeupdate 事件流畅；同时处理循环和「播放本段」
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const v = video.current;
      if (v) {
        const t = v.currentTime;
        const s = segRef.current;
        if (!v.paused && s && loopRef.current && t >= s.end) v.currentTime = s.start;
        else if (!v.paused && stopAt.current !== null && t >= stopAt.current) { v.pause(); stopAt.current = null; }
        setTime(v.currentTime);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const seek = useCallback((t: number) => {
    const v = video.current;
    if (v) v.currentTime = Math.max(0, t);
    setTime(t);
  }, []);

  const togglePlay = useCallback(() => {
    const v = video.current;
    if (!v) return;
    stopAt.current = null;
    if (v.paused) void v.play(); else v.pause();
  }, []);

  const playSeg = useCallback((s: Segment) => {
    const v = video.current;
    if (!v) return;
    v.currentTime = s.start;
    stopAt.current = loopRef.current ? null : s.end;
    void v.play();
  }, []);

  const save = useCallback(async () => {
    if (!p || saving) return;
    setSaving(true);
    try {
      const r = await api.save(p);
      dispatch({ type: "saved" });
      setSavedAt(r.saved_at);
      setError(null);
    } catch (e) {
      setError("保存失败：" + String((e as Error).message ?? e));
    } finally {
      setSaving(false);
    }
  }, [p, saving]);

  const visible = useMemo(() => {
    if (!p) return [];
    const q = search.trim();
    return p.segments.filter((s) => {
      if (spkFilter && s.speaker !== spkFilter && !s.overlap_speakers.includes(spkFilter)) return false;
      if (filter === "unreviewed" && s.reviewed) return false;
      if (filter === "flagged" && (s.reviewed || (!s.flags.length && s.type === "speech"))) return false;
      if (filter === "overlap" && s.type !== "overlap") return false;
      if (filter === "non_speech" && s.type !== "non_speech") return false;
      if (q && !s.text.includes(q) && !s.note.includes(q)) return false;
      return true;
    });
  }, [p, filter, spkFilter, search]);

  const selectRel = useCallback((d: number) => {
    if (!visible.length) return;
    const i = visible.findIndex((s) => s.id === selectedId);
    const j = i < 0 ? (d > 0 ? 0 : visible.length - 1) : Math.max(0, Math.min(visible.length - 1, i + d));
    const s = visible[j];
    setSelectedId(s.id);
    seek(s.start);
  }, [visible, selectedId, seek]);

  const patch = useCallback((patch: Partial<Segment>, key?: string) => {
    if (seg) dispatch({ type: "updateSeg", id: seg.id, patch, key });
  }, [seg]);

  const split = useCallback(() => {
    if (!seg) return;
    const newId = uid();
    dispatch({ type: "split", id: seg.id, at: time, newId });
  }, [seg, time]);

  const mergeNext = useCallback(() => { if (seg) dispatch({ type: "mergeNext", id: seg.id }); }, [seg]);

  const del = useCallback(() => {
    if (!seg || !p) return;
    const i = p.segments.findIndex((s) => s.id === seg.id);
    const next = p.segments[i + 1] ?? p.segments[i - 1];
    dispatch({ type: "delete", ids: [seg.id] });
    setSelectedId(next?.id ?? null);
  }, [seg, p]);

  // ---------- 快捷键 ----------
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); void save(); return; }
      if (typing) { if (e.key === "Escape") (e.target as HTMLElement).blur(); return; }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); dispatch({ type: e.shiftKey ? "redo" : "undo" }); return; }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") { e.preventDefault(); dispatch({ type: "redo" }); return; }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key;
      const step = e.shiftKey ? 0.1 : 0.02;
      const done = () => e.preventDefault();
      if (k === " ") { done(); togglePlay(); }
      else if (k === "ArrowDown" || k === "j") { done(); selectRel(1); }
      else if (k === "ArrowUp" || k === "k") { done(); selectRel(-1); }
      else if (k === "ArrowLeft") { done(); seek(time - (e.shiftKey ? 5 : 1)); }
      else if (k === "ArrowRight") { done(); seek(time + (e.shiftKey ? 5 : 1)); }
      else if (!seg) return;
      else if (k === "Enter" || k === "p") { done(); playSeg(seg); }
      else if (k === "l") { done(); setLoop((x) => !x); }
      else if (k === "r") { done(); patch({ reviewed: !seg.reviewed }); if (!seg.reviewed) selectRel(1); }
      else if (k === "s") { done(); split(); }
      else if (k === "m") { done(); mergeNext(); }
      else if (k === "Delete" || k === "Backspace") { done(); del(); }
      else if (k === "[") { done(); patch({ start: time }); }
      else if (k === "]") { done(); patch({ end: time }); }
      else if (k === "q" || k === "Q") { done(); patch({ start: seg.start - step }, "kq"); }
      else if (k === "w" || k === "W") { done(); patch({ start: seg.start + step }, "kw"); }
      else if (k === "o" || k === "O") { done(); patch({ end: seg.end - step }, "ko"); }
      else if (k === "i" || k === "I") { done(); patch({ end: seg.end + step }, "ki"); }
      else if (/^[1-9]$/.test(k) && p) {
        const spk = p.speakers[+k - 1];
        if (spk) { done(); patch({ type: "speech", speaker: spk.id }); }
      }
      else if (k === "x") { done(); patch({ type: "non_speech", speaker: null }); }
      else if (k === "v") { done(); patch({ type: "overlap", speaker: null }); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [save, togglePlay, selectRel, seek, time, seg, playSeg, patch, split, mergeNext, del, p]);

  useEffect(() => { if (video.current) video.current.playbackRate = rate; }, [rate]);

  if (error && !p) return <div className="pad"><button onClick={onBack}>← 返回</button><p className="error">{error}</p></div>;
  if (!p) return <div className="pad">加载中…</div>;

  const reviewed = p.segments.filter((s) => s.reviewed).length;
  const counts = {
    overlap: p.segments.filter((s) => s.type === "overlap").length,
    non_speech: p.segments.filter((s) => s.type === "non_speech").length,
    flagged: p.segments.filter((s) => !s.reviewed && (s.flags.length > 0 || s.type !== "speech")).length,
  };

  return (
    <div className="review">
      <header className="topbar">
        <button onClick={() => { if (!st.dirty || confirm("有未保存的修改，确定离开？")) onBack(); }}>← 项目列表</button>
        <b className="title" title={p.source_video}>{p.source_video.split(/[\\/]/).pop()}</b>
        <span className="muted">已核验 {reviewed}/{p.segments.length}</span>
        <progress value={reviewed} max={Math.max(1, p.segments.length)} />
        <span className="spacer" />
        <button onClick={() => dispatch({ type: "undo" })} disabled={!st.past.length} title="Ctrl+Z">↶ 撤销</button>
        <button onClick={() => dispatch({ type: "redo" })} disabled={!st.future.length} title="Ctrl+Shift+Z">↷ 重做</button>
        <button className="primary" onClick={() => void save()} disabled={saving || !st.dirty} title="Ctrl+S">
          {saving ? "保存中…" : st.dirty ? "保存 *" : "已保存"}
        </button>
        {savedAt && !st.dirty && <span className="muted small">{savedAt.slice(11)}</span>}
      </header>
      {error && <div className="error banner">{error} <button onClick={() => setError(null)}>×</button></div>}

      <div className="main">
        <div className="left">
          <video ref={video} src={api.mediaUrl(id)} preload="auto" className="player"
            onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
            onError={() => setError("媒体无法播放。若是 mkv/HEVC 等格式，请重跑 step1（MAKE_PREVIEW=\"always\"）生成预览视频")} />
          <div className="transport">
            <button onClick={togglePlay}>{playing ? "❚❚" : "▶"}</button>
            <span className="mono">{fmtTime(time)} / {fmtTime(p.duration, false)}</span>
            <select value={rate} onChange={(e) => setRate(+e.target.value)}>
              {[0.5, 0.75, 1, 1.25, 1.5, 2].map((r) => <option key={r} value={r}>{r}x</option>)}
            </select>
            <label className="check"><input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} />循环选中段</label>
          </div>
          <SpeakerPanel speakers={p.speakers} segments={p.segments} filter={spkFilter} onFilter={setSpkFilter}
            onRename={(sid, name) => dispatch({ type: "updateSpeaker", id: sid, patch: { name }, key: `name-${sid}` })}
            onColor={(sid, color) => dispatch({ type: "updateSpeaker", id: sid, patch: { color }, key: `color-${sid}` })}
            onAdd={() => dispatch({ type: "addSpeaker", id: newSpeakerId() })}
            onMerge={(from, into) => {
              const a = p.speakers.find((s) => s.id === from)?.name, b = p.speakers.find((s) => s.id === into)?.name;
              if (confirm(`把「${a}」的全部片段并入「${b}」？（可撤销）`)) {
                dispatch({ type: "mergeSpeaker", from, into });
                if (spkFilter === from) setSpkFilter(into);
              }
            }} />
          <details className="help">
            <summary>快捷键</summary>
            <table><tbody>
              <tr><td>空格</td><td>播放/暂停</td></tr>
              <tr><td>↑ ↓ / j k</td><td>上/下一段</td></tr>
              <tr><td>← →</td><td>后退/前进 1s（Shift 5s）</td></tr>
              <tr><td>Enter / P</td><td>播放本段</td></tr>
              <tr><td>L</td><td>循环本段</td></tr>
              <tr><td>R</td><td>标记已核验并跳到下一段</td></tr>
              <tr><td>1-9</td><td>改为第 N 个说话人</td></tr>
              <tr><td>X / V</td><td>标为非人声 / 多人重叠</td></tr>
              <tr><td>[ ]</td><td>起点/终点设到播放头</td></tr>
              <tr><td>Q W</td><td>起点左/右微调（Shift 加大）</td></tr>
              <tr><td>O I</td><td>终点左/右微调（Shift 加大）</td></tr>
              <tr><td>S</td><td>在播放头拆分</td></tr>
              <tr><td>M</td><td>与下一段合并</td></tr>
              <tr><td>Delete</td><td>删除片段</td></tr>
              <tr><td>Ctrl+Z / Ctrl+Shift+Z</td><td>撤销 / 重做</td></tr>
              <tr><td>Ctrl+S</td><td>保存</td></tr>
            </tbody></table>
          </details>
        </div>

        <div className="right">
          <div className="filters">
            {([["all", `全部 ${p.segments.length}`], ["unreviewed", `未核验 ${p.segments.length - reviewed}`],
               ["flagged", `待关注 ${counts.flagged}`], ["overlap", `重叠 ${counts.overlap}`],
               ["non_speech", `非人声 ${counts.non_speech}`]] as [Filter, string][]).map(([k, label]) => (
              <button key={k} className={filter === k ? "on" : ""} onClick={() => setFilter(k)}>{label}</button>
            ))}
            <input className="search" placeholder="搜索文字…" value={search} onChange={(e) => setSearch(e.target.value)} />
            {spkFilter && <span className="flag">只看：{p.speakers.find((s) => s.id === spkFilter)?.name}
              <button className="link" onClick={() => setSpkFilter(null)}>×</button></span>}
          </div>
          <SegmentList segments={visible} speakers={p.speakers} selectedId={selectedId} activeId={activeId}
            onSelect={(sid) => { setSelectedId(sid); const s = p.segments.find((x) => x.id === sid); if (s) seek(s.start); }} />
          {seg ? (
            <SegmentEditor key={seg.id} seg={seg} speakers={p.speakers} time={time} onPatch={patch}
              onSplit={split} onMergeNext={mergeNext} onDelete={del} onPlay={() => playSeg(seg)}
              onLoop={() => setLoop((x) => !x)} looping={loop} />
          ) : (
            <div className="editor muted">选择一个片段进行编辑。也可以在下方时间轴的空白处拖动来新建片段。</div>
          )}
        </div>
      </div>

      <Timeline duration={p.duration} peaks={peaks} segments={p.segments} speakers={p.speakers} time={time}
        playing={playing} selectedId={selectedId} onSeek={seek} onSelect={setSelectedId}
        onResize={(sid, s, e, key) => dispatch({ type: "updateSeg", id: sid, patch: { start: s, end: e }, key })}
        onCreate={(speaker, s, e) => {
          const nid = uid();
          dispatch({ type: "add", seg: { id: nid, start: s, end: e, type: speaker ? "speech" : "non_speech",
            speaker, overlap_speakers: [], text: "", words: [], confidence: null, note: speaker ? "" : "人工添加",
            flags: [], reviewed: false } });
          setSelectedId(nid);
        }} />
    </div>
  );
}
