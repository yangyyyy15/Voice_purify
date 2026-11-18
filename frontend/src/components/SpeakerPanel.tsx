import { useState } from "react";
import type { Segment, Speaker } from "../types";

interface Props {
  speakers: Speaker[];
  segments: Segment[];
  filter: string | null;
  onFilter: (id: string | null) => void;
  onRename: (id: string, name: string) => void;
  onColor: (id: string, color: string) => void;
  onAdd: () => void;
  onMerge: (from: string, into: string) => void;
}

export function SpeakerPanel({ speakers, segments, filter, onFilter, onRename, onColor, onAdd, onMerge }: Props) {
  const [mergeFrom, setMergeFrom] = useState<string | null>(null);
  const stats = new Map<string, { n: number; dur: number }>();
  for (const s of segments) {
    if (s.type !== "speech" || !s.speaker) continue;
    const x = stats.get(s.speaker) ?? { n: 0, dur: 0 };
    x.n += 1;
    x.dur += s.end - s.start;
    stats.set(s.speaker, x);
  }
  return (
    <div className="speakers">
      <div className="panel-title">说话人 <button onClick={onAdd}>＋ 新增</button></div>
      {speakers.map((s, i) => {
        const st = stats.get(s.id) ?? { n: 0, dur: 0 };
        return (
          <div key={s.id} className={"speaker" + (filter === s.id ? " active" : "")}>
            <input type="color" value={s.color} onChange={(e) => onColor(s.id, e.target.value)} />
            <input className="speaker-name" value={s.name} onChange={(e) => onRename(s.id, e.target.value)}
              title={s.id} />
            <span className="muted small">{i < 9 ? `键${i + 1} · ` : ""}{st.n}段 {Math.round(st.dur)}s</span>
            <button className="small" onClick={() => onFilter(filter === s.id ? null : s.id)} title="只看此人">
              {filter === s.id ? "全部" : "筛选"}
            </button>
            {mergeFrom === s.id ? (
              <select autoFocus defaultValue="" onBlur={() => setMergeFrom(null)}
                onChange={(e) => { if (e.target.value) onMerge(s.id, e.target.value); setMergeFrom(null); }}>
                <option value="" disabled>并入…</option>
                {speakers.filter((x) => x.id !== s.id).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            ) : (
              <button className="small" disabled={speakers.length < 2} onClick={() => setMergeFrom(s.id)}
                title="把此人的所有片段并入另一个说话人（同一人被拆成两个时用）">合并</button>
            )}
          </div>
        );
      })}
    </div>
  );
}
