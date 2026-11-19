"""
project.json 数据结构。流水线写它，UI 读写它。
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = 1

SegmentType = Literal["speech", "overlap", "non_speech"]


class Word(BaseModel):
    word: str
    start: float
    end: float
    prob: Optional[float] = None  # 只有 Whisper 后端提供


class Speaker(BaseModel):
    id: str               # SPEAKER_00 ...（流水线生成，人工新增的用 SPK_xxx）
    name: str = "未命名"
    color: str = "#3498db"


class Segment(BaseModel):
    id: str
    start: float
    end: float
    type: SegmentType = "speech"
    speaker: Optional[str] = None            # speech 段的说话人 id
    overlap_speakers: List[str] = []         # overlap 段涉及的说话人
    text: str = ""
    words: List[Word] = []
    confidence: Optional[float] = None
    note: str = ""                           # 例如非人声原因 "Ringtone"
    flags: List[str] = []                    # low_conf / short / no_text / low_vad / noise / no_speaker
    reviewed: bool = False

    @model_validator(mode="after")
    def _check_times(self):
        if self.end <= self.start:
            raise ValueError(f"片段 {self.id}: end({self.end}) 必须大于 start({self.start})")
        if self.start < 0:
            raise ValueError(f"片段 {self.id}: start 不能为负")
        return self


class Project(BaseModel):
    schema_version: int = SCHEMA_VERSION
    video_id: str
    source_video: str
    media: str                    # UI 播放用的文件（原视频或转码预览）
    peaks: str                    # 波形峰值 json
    audio_analysis: str           # 16k 分析音轨（人声轨）
    audio_export: str             # 48k 原始音轨，导出用
    audio_export_raw: Optional[str] = None
    audio_export_compensated: Optional[str] = None
    segment_audio_exports: dict = Field(default_factory=dict)
    duration: float
    created_at: str = ""
    pipeline_params: dict = Field(default_factory=dict)
    speakers: List[Speaker] = []
    segments: List[Segment] = []
