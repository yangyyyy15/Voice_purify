export type SegType = "speech" | "overlap" | "non_speech";

export interface Word {
  word: string;
  start: number;
  end: number;
  prob?: number | null;
}

export interface Speaker {
  id: string;
  name: string;
  color: string;
}

export interface Segment {
  id: string;
  start: number;
  end: number;
  type: SegType;
  speaker: string | null;
  overlap_speakers: string[];
  text: string;
  words: Word[];
  confidence: number | null;
  note: string;
  flags: string[];
  reviewed: boolean;
}

export interface Project {
  schema_version: number;
  video_id: string;
  source_video: string;
  media: string;
  peaks: string;
  audio_analysis: string;
  audio_export: string;
  audio_export_raw?: string | null;
  audio_export_compensated?: string | null;
  duration: number;
  created_at: string;
  pipeline_params: Record<string, unknown>;
  speakers: Speaker[];
  segments: Segment[];
}

export interface ProjectSummary {
  id: string;
  source: string;
  duration: number;
  speakers: number;
  segments: number;
  reviewed: number;
  modified: string;
}

export const FLAG_LABELS: Record<string, string> = {
  low_conf: "低置信",
  short: "过短",
  no_text: "无文字",
  low_vad: "疑似非语音",
  noise: "有噪音",
  no_speaker: "无说话人",
};

export const TYPE_LABELS: Record<SegType, string> = {
  speech: "说话",
  overlap: "多人重叠",
  non_speech: "非人声",
};
