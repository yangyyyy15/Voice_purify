import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Segment, Speaker } from "../types";
import { fmtTime } from "../util";

interface Props {
  duration: number;
  peaks: { rate: number; data: number[] } | null;
  segments: Segment[];
  speakers: Speaker[];
  time: number;
  playing: boolean;
  selectedId: string | null;
  onSeek: (t: number) => void;
  onSelect: (id: string | null) => void;
  onResize: (id: string, start: number, end: number, key: string) => void;
  onCreate: (speaker: string | null, start: number, end: number) => void;
}

const GUTTER = 96, RULER = 20, WAVE = 64, LANE = 26, EDGE_PX = 6, MIN_PPS = 0.5, MAX_PPS = 800;
const OTHER = "__other__";

type Drag =
  | { kind: "resize"; id: string; edge: "start" | "end"; key: string; fixed: number }
  | { kind: "create"; lane: string; x0: number; t0: number; t1: number; moved: boolean }
  | { kind: "pan"; x0: number; view0: number }
  | { kind: "seek" };

export function Timeline(p: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(800);
  const [pps, setPps] = useState(20);             // 每秒像素
  const [view, setView] = useState(0);            // 视野左端时间
  const drag = useRef<Drag | null>(null);
  const [ghost, setGhost] = useState<{ lane: string; t0: number; t1: number } | null>(null);
  const [hoverCursor, setHoverCursor] = useState("default");

  const lanes = [...p.speakers.map((s) => s.id), OTHER];
  const height = RULER + WAVE + lanes.length * LANE + 4;
  const area = Math.max(10, width - GUTTER);
  const visible = area / pps;
  const maxView = Math.max(0, p.duration - visible);

  const clampView = useCallback((v: number) => Math.max(0, Math.min(v, Math.max(0, p.duration - area / pps))), [p.duration, area, pps]);
  const xOf = (t: number) => GUTTER + (t - view) * pps;
  const tOf = (x: number) => Math.max(0, Math.min(p.duration, view + (x - GUTTER) / pps));
  const laneOf = (s: Segment) => (s.type === "speech" && s.speaker && p.speakers.some((k) => k.id === s.speaker) ? s.speaker : OTHER);
  const laneY = (lane: string) => RULER + WAVE + lanes.indexOf(lane) * LANE;

  useLayoutEffect(() => {
    if (!wrap.current) return;
    const ro = new ResizeObserver((e) => setWidth(Math.floor(e[0].contentRect.width)));
    ro.observe(wrap.current);
    return () => ro.disconnect();
  }, []);

  // 首次加载：缩放到合适比例（约显示 60 秒）
  const inited = useRef(false);
  useEffect(() => {
    if (inited.current || !p.duration || width < 100) return;
    inited.current = true;
    setPps(Math.max(MIN_PPS, Math.min(MAX_PPS, (width - GUTTER) / Math.min(60, p.duration))));
  }, [p.duration, width]);

  // 播放时自动翻页
  useEffect(() => {
    if (!p.playing || drag.current) return;
    if (p.time < view || p.time > view + visible * 0.92) setView(clampView(p.time - visible * 0.08));
  }, [p.time, p.playing, view, visible, clampView]);

  // 选中片段在视野外时滚动过去
  useEffect(() => {
    const s = p.segments.find((x) => x.id === p.selectedId);
    if (!s || drag.current) return;
    if (s.end < view || s.start > view + visible) setView(clampView(s.start - visible * 0.2));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.selectedId]);

  // ---------- 绘制 ----------
  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = width * dpr;
    c.height = height * dpr;
    const g = c.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.fillStyle = "#fafafa";
    g.fillRect(0, 0, width, height);
    const t0 = view, t1 = view + visible;

    // 刻度
    const steps = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600];
    const step = steps.find((s) => s * pps >= 70) ?? 3600;
    g.fillStyle = "#666";
    g.font = "11px sans-serif";
    g.strokeStyle = "#ddd";
    g.beginPath();
    for (let t = Math.ceil(t0 / step) * step; t <= t1; t += step) {
      const x = Math.round(xOf(t)) + 0.5;
      g.moveTo(x, RULER - 6);
      g.lineTo(x, height);
      g.fillText(fmtTime(t, step < 1), x + 3, 12);
    }
    g.stroke();

    // 波形
    if (p.peaks && p.peaks.data.length) {
      const { rate, data } = p.peaks;
      const mid = RULER + WAVE / 2;
      g.fillStyle = "#7a8ca3";
      for (let x = GUTTER; x < width; x++) {
        const a = Math.floor(tOf(x) * rate), b = Math.max(a + 1, Math.floor(tOf(x + 1) * rate));
        let m = 0;
        for (let i = a; i < b && i < data.length; i++) if (data[i] > m) m = data[i];
        const h = Math.max(1, m * (WAVE / 2 - 2));
        g.fillRect(x, mid - h, 1, h * 2);
      }
    }

    // 轨道
    lanes.forEach((_lane, i) => {
      const y = RULER + WAVE + i * LANE;
      g.fillStyle = i % 2 ? "#f2f2f2" : "#fcfcfc";
      g.fillRect(GUTTER, y, width - GUTTER, LANE);
    });

    // 片段
    const spk = new Map(p.speakers.map((s) => [s.id, s]));
    g.font = "12px sans-serif";
    for (const s of p.segments) {
      if (s.end < t0 || s.start > t1) continue;
      const x0 = Math.max(GUTTER, xOf(s.start)), x1 = Math.min(width, xOf(s.end));
      const y = laneY(laneOf(s)) + 3, h = LANE - 6;
      const color = s.type === "overlap" ? "#f5b400" : s.type === "non_speech" ? "#9e9e9e"
        : spk.get(s.speaker ?? "")?.color ?? "#555";
      g.globalAlpha = s.reviewed ? 0.85 : 0.5;
      g.fillStyle = color;
      g.fillRect(x0, y, Math.max(1, x1 - x0), h);
      g.globalAlpha = 1;
      if (s.type === "overlap") {           // 斜线纹理
        g.save();
        g.beginPath();
        g.rect(x0, y, x1 - x0, h);
        g.clip();
        g.strokeStyle = "rgba(0,0,0,0.35)";
        for (let x = x0 - h; x < x1; x += 7) { g.moveTo(x, y + h); g.lineTo(x + h, y); }
        g.stroke();
        g.restore();
      }
      if (s.flags.length && !s.reviewed) {
        g.fillStyle = "#d32f2f";
        g.fillRect(x0, y, Math.min(4, x1 - x0), h);
      }
      if (s.id === p.selectedId) {
        g.strokeStyle = "#111";
        g.lineWidth = 2;
        g.strokeRect(x0 + 1, y - 1, Math.max(1, x1 - x0 - 2), h + 2);
        g.lineWidth = 1;
      }
      const label = s.type === "speech" ? s.text : s.type === "overlap" ? "多人重叠" : s.note || "非人声";
      if (x1 - x0 > 24 && label) {
        g.save();
        g.beginPath();
        g.rect(x0 + 3, y, x1 - x0 - 6, h);
        g.clip();
        g.fillStyle = "#111";
        g.fillText(label, x0 + 5, y + h - 6);
        g.restore();
      }
    }

    if (ghost) {
      const x0 = xOf(Math.min(ghost.t0, ghost.t1)), x1 = xOf(Math.max(ghost.t0, ghost.t1));
      g.strokeStyle = "#1565c0";
      g.setLineDash([4, 3]);
      g.strokeRect(x0, laneY(ghost.lane) + 3, x1 - x0, LANE - 6);
      g.setLineDash([]);
    }

    // 超出时长的部分置灰
    const xEnd = xOf(p.duration);
    if (xEnd < width) {
      g.fillStyle = "#e0e0e0";
      g.fillRect(Math.max(GUTTER, xEnd), 0, width - Math.max(GUTTER, xEnd), height);
    }

    // 左侧轨道名
    g.fillStyle = "#fff";
    g.fillRect(0, 0, GUTTER, height);
    g.fillStyle = "#333";
    g.fillText("波形", 8, RULER + WAVE / 2 + 4);
    lanes.forEach((lane, i) => {
      const y = RULER + WAVE + i * LANE;
      const s = spk.get(lane);
      g.fillStyle = s ? s.color : "#999";
      g.fillRect(6, y + 8, 10, 10);
      g.fillStyle = "#222";
      const name = s ? s.name : "重叠/非人声";
      g.fillText(name.length > 7 ? name.slice(0, 7) + "…" : name, 22, y + 17);
    });
    g.strokeStyle = "#ccc";
    g.beginPath();
    g.moveTo(GUTTER - 0.5, 0);
    g.lineTo(GUTTER - 0.5, height);
    g.stroke();

    // 播放头
    if (p.time >= t0 && p.time <= t1) {
      const x = Math.round(xOf(p.time)) + 0.5;
      g.strokeStyle = "#e53935";
      g.lineWidth = 1.5;
      g.beginPath();
      g.moveTo(x, 0);
      g.lineTo(x, height);
      g.stroke();
      g.lineWidth = 1;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, height, pps, view, p.peaks, p.segments, p.speakers, p.time, p.selectedId, ghost]);

  // ---------- 交互 ----------
  const hit = (x: number, y: number) => {
    if (x < GUTTER || y < RULER + WAVE) return null;
    const li = Math.floor((y - RULER - WAVE) / LANE);
    const lane = lanes[li];
    if (!lane) return null;
    const t = tOf(x);
    let best: { seg: Segment; edge: "start" | "end" | null } | null = null;
    for (const s of p.segments) {
      if (laneOf(s) !== lane) continue;
      const xs = xOf(s.start), xe = xOf(s.end);
      if (Math.abs(x - xs) <= EDGE_PX && (!best || s.id === p.selectedId)) best = { seg: s, edge: "start" };
      else if (Math.abs(x - xe) <= EDGE_PX && (!best || s.id === p.selectedId)) best = { seg: s, edge: "end" };
      else if (!best && t >= s.start && t <= s.end) best = { seg: s, edge: null };
    }
    return { lane, best };
  };

  const pos = (e: React.PointerEvent | React.WheelEvent) => {
    const r = canvas.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  const onDown = (e: React.PointerEvent) => {
    const { x, y } = pos(e);
    canvas.current!.setPointerCapture(e.pointerId);
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      drag.current = { kind: "pan", x0: x, view0: view };
      return;
    }
    if (e.button !== 0) return;
    const h = hit(x, y);
    if (h?.best?.edge) {
      const s = h.best.seg;
      p.onSelect(s.id);
      drag.current = { kind: "resize", id: s.id, edge: h.best.edge, key: `drag-${s.id}-${Date.now()}`,
        fixed: h.best.edge === "start" ? s.end : s.start };
    } else if (h?.best) {
      p.onSelect(h.best.seg.id);
      p.onSeek(h.best.seg.start);
      drag.current = null;
    } else if (h) {
      const t = tOf(x);
      drag.current = { kind: "create", lane: h.lane, x0: x, t0: t, t1: t, moved: false };
    } else {
      drag.current = { kind: "seek" };
      p.onSeek(tOf(x));
    }
  };

  const onMove = (e: React.PointerEvent) => {
    const { x, y } = pos(e);
    const d = drag.current;
    if (!d) {
      const h = hit(x, y);
      setHoverCursor(h?.best?.edge ? "ew-resize" : h?.best ? "pointer" : x >= GUTTER ? "crosshair" : "default");
      return;
    }
    if (d.kind === "pan") setView(clampView(d.view0 - (x - d.x0) / pps));
    else if (d.kind === "seek") p.onSeek(tOf(x));
    else if (d.kind === "resize") {
      const t = tOf(x);
      const [s, en] = d.edge === "start" ? [Math.min(t, d.fixed - 0.05), d.fixed] : [d.fixed, Math.max(t, d.fixed + 0.05)];
      p.onResize(d.id, s, en, d.key);
    } else if (d.kind === "create") {
      d.t1 = tOf(x);
      d.moved = d.moved || Math.abs(x - d.x0) > 4;
      if (d.moved) setGhost({ lane: d.lane, t0: d.t0, t1: d.t1 });
    }
  };

  const onUp = () => {
    const d = drag.current;
    drag.current = null;
    if (d?.kind === "create") {
      setGhost(null);
      if (d.moved && Math.abs(d.t1 - d.t0) >= 0.1) {
        p.onCreate(d.lane === OTHER ? null : d.lane, Math.min(d.t0, d.t1), Math.max(d.t0, d.t1));
      } else {
        p.onSelect(null);
        p.onSeek(d.t0);
      }
    }
  };

  const zoomAt = (factor: number, x = GUTTER + area / 2) => {
    const t = tOf(x);
    const np = Math.max(MIN_PPS, Math.min(MAX_PPS, pps * factor));
    setPps(np);
    setView(Math.max(0, Math.min(t - (x - GUTTER) / np, Math.max(0, p.duration - area / np))));
  };

  // wheel 需要 passive:false 才能 preventDefault
  const wheelRef = useRef<(e: WheelEvent) => void>(() => {});
  wheelRef.current = (e: WheelEvent) => {
    e.preventDefault();
    const r = canvas.current!.getBoundingClientRect();
    if (e.ctrlKey || e.metaKey) zoomAt(e.deltaY < 0 ? 1.25 : 0.8, e.clientX - r.left);
    else setView((v) => clampView(v + ((Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY) / pps)));
  };
  useEffect(() => {
    const c = canvas.current!;
    const h = (e: WheelEvent) => wheelRef.current(e);
    c.addEventListener("wheel", h, { passive: false });
    return () => c.removeEventListener("wheel", h);
  }, []);

  return (
    <div className="timeline" ref={wrap}>
      <div className="timeline-bar">
        <button onClick={() => zoomAt(1.5)} title="放大 (Ctrl+滚轮)">＋</button>
        <button onClick={() => zoomAt(1 / 1.5)} title="缩小">－</button>
        <button onClick={() => { setPps(Math.max(MIN_PPS, area / Math.max(1, p.duration))); setView(0); }}>全部</button>
        <button onClick={() => { setPps(area / 30); setView(clampView(p.time - 5)); }}>30秒</button>
        <input type="range" min={0} max={Math.max(0.001, maxView)} step={0.01} value={Math.min(view, maxView)}
          onChange={(e) => setView(+e.target.value)} className="timeline-scroll" />
        <span className="hint">拖边界调整 · 空白处拖动新建 · 滚轮平移 · Ctrl+滚轮缩放 · Alt+拖动平移</span>
      </div>
      <canvas ref={canvas} style={{ width, height, cursor: hoverCursor, display: "block" }}
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}
        onContextMenu={(e) => e.preventDefault()} />
    </div>
  );
}
