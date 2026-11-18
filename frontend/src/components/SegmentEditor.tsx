import { useEffect, useState } from "react";
import type { Segment, SegType, Speaker } from "../types";
import { FLAG_LABELS, TYPE_LABELS } from "../types";
import { fmtTime, parseTime } from "../util";

interface Props {
  seg: Segment;
  speakers: Speaker[];
  time: number;
  onPatch: (patch: Partial<Segment>, key?: string) => void;
  onSplit: () => void;
  onMergeNext: () => void;
  onDelete: () => void;
  onPlay: () => void;
  onLoop: () => void;
  looping: boolean;
}

function TimeInput({ value, onCommit }: { value: number; onCommit: (t: number) => void }) {
  const [txt, setTxt] = useState(fmtTime(value));
  const [bad, setBad] = useState(false);
  useEffect(() => { setTxt(fmtTime(value)); setBad(false); }, [value]);
  const commit = () => {
    const t = parseTime(txt);
    if (t === null) { setBad(true); return; }
    onCommit(t);
  };
  return (
    <input className={"time-input" + (bad ? " bad" : "")} value={txt}
      onChange={(e) => setTxt(e.target.value)} onBlur={commit}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
  );
}

export function SegmentEditor({ seg, speakers, time, onPatch, onSplit, onMergeNext, onDelete, onPlay, onLoop, looping }: Props) {
  const canSplit = time > seg.start + 0.05 && time < seg.end - 0.05;
  return (
    <div className="editor">
      <div className="editor-row">
        <TimeInput value={seg.start} onCommit={(t) => onPatch({ start: t })} />
        <span>→</span>
        <TimeInput value={seg.end} onCommit={(t) => onPatch({ end: t })} />
        <span className="muted">时长 {(seg.end - seg.start).toFixed(2)}s</span>
        <button onClick={() => onPatch({ start: seg.start - 0.1 }, "nudge-s")} title="起点左移 0.1s">[←</button>
        <button onClick={() => onPatch({ start: seg.start + 0.1 }, "nudge-s")} title="起点右移 0.1s">[→</button>
        <button onClick={() => onPatch({ end: seg.end - 0.1 }, "nudge-e")} title="终点左移 0.1s">←]</button>
        <button onClick={() => onPatch({ end: seg.end + 0.1 }, "nudge-e")} title="终点右移 0.1s">→]</button>
        <button onClick={() => onPatch({ start: time })} title="把起点设到播放头 ([)">起点=播放头</button>
        <button onClick={() => onPatch({ end: time })} title="把终点设到播放头 (])">终点=播放头</button>
      </div>
      <div className="editor-row">
        <label>类型
          <select value={seg.type} onChange={(e) => onPatch({ type: e.target.value as SegType })}>
            {(Object.keys(TYPE_LABELS) as SegType[]).map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
          </select>
        </label>
        {seg.type === "speech" && (
          <label>说话人
            <select value={seg.speaker ?? ""} onChange={(e) => onPatch({ speaker: e.target.value || null })}>
              <option value="">（未指定）</option>
              {speakers.map((s, i) => <option key={s.id} value={s.id}>{i < 9 ? `${i + 1}. ` : ""}{s.name}</option>)}
            </select>
          </label>
        )}
        {seg.type === "overlap" && seg.overlap_speakers.length > 0 && (
          <span className="muted">涉及：{seg.overlap_speakers.map((id) => speakers.find((s) => s.id === id)?.name ?? id).join("、")}</span>
        )}
        {seg.confidence != null && <span className="muted">置信度 {seg.confidence.toFixed(2)}</span>}
        {seg.flags.map((f) => <span key={f} className="flag">{FLAG_LABELS[f] ?? f}</span>)}
      </div>
      {seg.type === "speech" ? (
        <textarea className="editor-text" value={seg.text} rows={3}
          onChange={(e) => onPatch({ text: e.target.value }, `text-${seg.id}`)} placeholder="（无文字）" />
      ) : (
        <div className="muted editor-note">{seg.type === "overlap" ? "多人同时说话，不做转写。" : "非人声片段。"} {seg.note}</div>
      )}
      <div className="editor-row">
        <button onClick={onPlay} title="播放本段 (P)">▶ 播放本段</button>
        <button onClick={onLoop} className={looping ? "on" : ""} title="循环播放 (L)">⟳ 循环</button>
        <button onClick={onSplit} disabled={!canSplit} title="在播放头处拆分 (S)">✂ 在播放头拆分</button>
        <button onClick={onMergeNext} title="与下一段合并 (M)">⇥ 合并下一段</button>
        <button onClick={onDelete} className="danger" title="删除 (Delete)">删除</button>
        <span className="spacer" />
        <label className="check">
          <input type="checkbox" checked={seg.reviewed} onChange={(e) => onPatch({ reviewed: e.target.checked })} />
          已核验 (R)
        </label>
      </div>
    </div>
  );
}
