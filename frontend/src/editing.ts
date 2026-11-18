import type { Project, Segment, Speaker } from "./types";
import { joinTexts, joinWords, round3, uid } from "./util";

export const MIN_LEN = 0.05;
const HISTORY_LIMIT = 200;
const PALETTE = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6",
  "#9a6324", "#469990", "#808000", "#000075", "#e6beff", "#aaffc3", "#ffd8b1"];

export interface EditState {
  project: Project | null;
  past: Project[];
  future: Project[];
  dirty: boolean;
  lastKey: string | null;  // 连续同 key 的修改（拖拽、打字）合并成一步撤销
}

export const initialEdit: EditState = { project: null, past: [], future: [], dirty: false, lastKey: null };

export type Action =
  | { type: "load"; project: Project }
  | { type: "saved" }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "updateSeg"; id: string; patch: Partial<Segment>; key?: string }
  | { type: "updateMany"; ids: string[]; patch: Partial<Segment> }
  | { type: "split"; id: string; at: number; newId: string }
  | { type: "mergeNext"; id: string }
  | { type: "delete"; ids: string[] }
  | { type: "add"; seg: Segment }
  | { type: "updateSpeaker"; id: string; patch: Partial<Speaker>; key?: string }
  | { type: "addSpeaker"; id: string }
  | { type: "mergeSpeaker"; from: string; into: string };

const sortSegs = (segs: Segment[]) => segs.sort((a, b) => a.start - b.start || a.end - b.end);

function clampTimes(s: Segment, duration: number): Segment {
  let start = round3(Math.max(0, Math.min(s.start, duration - MIN_LEN)));
  let end = round3(Math.min(duration, Math.max(s.end, start + MIN_LEN)));
  if (end - start < MIN_LEN) start = round3(end - MIN_LEN);
  return { ...s, start, end };
}

function apply(p: Project, a: Action): Project | null {
  const segs = p.segments;
  switch (a.type) {
    case "updateSeg": {
      const i = segs.findIndex((s) => s.id === a.id);
      if (i < 0) return null;
      let s = { ...segs[i], ...a.patch };
      if ("text" in a.patch && !("words" in a.patch)) s.words = [];  // 人工改了文字，字级时间戳作废
      if (a.patch.type && a.patch.type !== "speech") s.speaker = a.patch.speaker ?? null;
      if (a.patch.type === "speech" && !s.speaker) s.speaker = p.speakers[0]?.id ?? null;
      s = clampTimes(s, p.duration);
      const next = segs.slice();
      next[i] = s;
      return { ...p, segments: "start" in a.patch || "end" in a.patch ? sortSegs(next) : next };
    }
    case "updateMany": {
      const ids = new Set(a.ids);
      return { ...p, segments: segs.map((s) => (ids.has(s.id) ? { ...s, ...a.patch } : s)) };
    }
    case "split": {
      const i = segs.findIndex((s) => s.id === a.id);
      if (i < 0) return null;
      const s = segs[i];
      if (a.at <= s.start + MIN_LEN || a.at >= s.end - MIN_LEN) return null;
      const at = round3(a.at);
      const left = s.words.filter((w) => (w.start + w.end) / 2 < at);
      const right = s.words.filter((w) => (w.start + w.end) / 2 >= at);
      const hasWords = s.words.length > 0;
      const first: Segment = { ...s, end: at, words: left, reviewed: false,
        text: hasWords ? joinWords(left.map((w) => w.word)) : s.text };
      const second: Segment = { ...s, id: a.newId, start: at, words: right, reviewed: false,
        text: hasWords ? joinWords(right.map((w) => w.word)) : "" };
      const next = segs.slice();
      next.splice(i, 1, first, second);
      return { ...p, segments: next };
    }
    case "mergeNext": {
      const i = segs.findIndex((s) => s.id === a.id);
      if (i < 0 || i + 1 >= segs.length) return null;
      const s = segs[i], n = segs[i + 1];
      const merged: Segment = { ...s, start: Math.min(s.start, n.start), end: Math.max(s.end, n.end),
        text: joinTexts(s.text, n.text), words: [...s.words, ...n.words],
        flags: Array.from(new Set([...s.flags, ...n.flags])), reviewed: false,
        overlap_speakers: Array.from(new Set([...s.overlap_speakers, ...n.overlap_speakers])),
        note: [s.note, n.note].filter(Boolean).join(" | ") };
      const next = segs.slice();
      next.splice(i, 2, merged);
      return { ...p, segments: next };
    }
    case "delete": {
      const ids = new Set(a.ids);
      return { ...p, segments: segs.filter((s) => !ids.has(s.id)) };
    }
    case "add":
      return { ...p, segments: sortSegs([...segs, clampTimes(a.seg, p.duration)]) };
    case "updateSpeaker":
      return { ...p, speakers: p.speakers.map((s) => (s.id === a.id ? { ...s, ...a.patch } : s)) };
    case "addSpeaker": {
      const n = p.speakers.length;
      return { ...p, speakers: [...p.speakers, { id: a.id, name: `说话人${n + 1}`, color: PALETTE[n % PALETTE.length] }] };
    }
    case "mergeSpeaker": {
      if (a.from === a.into) return null;
      return {
        ...p,
        speakers: p.speakers.filter((s) => s.id !== a.from),
        segments: segs.map((s) => ({
          ...s,
          speaker: s.speaker === a.from ? a.into : s.speaker,
          overlap_speakers: Array.from(new Set(s.overlap_speakers.map((x) => (x === a.from ? a.into : x)))),
        })),
      };
    }
    default:
      return null;
  }
}

export function editReducer(st: EditState, a: Action): EditState {
  switch (a.type) {
    case "load":
      return { ...initialEdit, project: a.project };
    case "saved":
      return { ...st, dirty: false, lastKey: null };
    case "undo": {
      if (!st.project || !st.past.length) return st;
      const prev = st.past[st.past.length - 1];
      return { project: prev, past: st.past.slice(0, -1), future: [st.project, ...st.future], dirty: true, lastKey: null };
    }
    case "redo": {
      if (!st.project || !st.future.length) return st;
      return { project: st.future[0], past: [...st.past, st.project], future: st.future.slice(1), dirty: true, lastKey: null };
    }
  }
  if (!st.project) return st;
  const next = apply(st.project, a);
  if (!next) return st;
  const key = "key" in a && a.key ? a.key : null;
  const coalesce = key !== null && key === st.lastKey;
  return {
    project: next,
    past: coalesce ? st.past : [...st.past, st.project].slice(-HISTORY_LIMIT),
    future: [],
    dirty: true,
    lastKey: key,
  };
}

export const newSpeakerId = () => uid("SPK_");
