import { useEffect, useRef } from "react";
import type { Segment, Speaker } from "../types";
import { FLAG_LABELS } from "../types";
import { fmtTime } from "../util";

interface Props {
  segments: Segment[];
  speakers: Speaker[];
  selectedId: string | null;
  activeId: string | null;   // 播放头所在片段
  onSelect: (id: string) => void;
}

export function SegmentList({ segments, speakers, selectedId, activeId, onSelect }: Props) {
  const spk = new Map(speakers.map((s) => [s.id, s]));
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = box.current?.querySelector<HTMLElement>(`[data-id="${selectedId}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);
  return (
    <div className="seglist" ref={box}>
      {segments.length === 0 && <div className="muted pad">没有符合条件的片段</div>}
      {segments.map((s) => {
        const sp = s.speaker ? spk.get(s.speaker) : undefined;
        const who = s.type === "overlap" ? "⚠ 多人重叠" : s.type === "non_speech" ? `🔇 ${s.note || "非人声"}` : sp?.name ?? "（未指定）";
        const color = s.type === "overlap" ? "#f5b400" : s.type === "non_speech" ? "#9e9e9e" : sp?.color ?? "#555";
        return (
          <div key={s.id} data-id={s.id} onClick={() => onSelect(s.id)}
            className={"segrow" + (s.id === selectedId ? " selected" : "") + (s.id === activeId ? " active" : "") + (s.reviewed ? " reviewed" : "")}>
            <span className="swatch" style={{ background: color }} />
            <span className="segtime">{fmtTime(s.start)}</span>
            <span className="segwho">{who}</span>
            <span className="segtext">{s.type === "speech" ? s.text || <i className="muted">（无文字）</i> : ""}</span>
            <span className="segflags">
              {!s.reviewed && s.flags.map((f) => <span key={f} className="flag small">{FLAG_LABELS[f] ?? f}</span>)}
              {s.reviewed && <span className="ok">✓</span>}
            </span>
          </div>
        );
      })}
    </div>
  );
}
