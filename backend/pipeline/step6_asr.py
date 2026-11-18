"""
Step 6：语音识别，输出带时间戳的 token 列表：
  {"words": [{"word": "今", "start": 1.2, "end": 1.4, "prob": None}, ...], "backend": ..., "inexact_spans": n}

后端：
  funasr  Paraformer-zh + fsmn-vad + ct-punc（中文默认）
  whisper faster-whisper large-v3（中英混说备选）
"""
from pathlib import Path

from .. import config
from .common import log
from .textutil import align_tokens, clean_whisper_word


def _funasr(audio: Path, device: str, hotwords: str) -> dict:
    from funasr import AutoModel

    model = AutoModel(model=config.FUNASR_MODEL, vad_model=config.FUNASR_VAD_MODEL,
                      punc_model=config.FUNASR_PUNC_MODEL, device=device, disable_update=True)
    kwargs = {"batch_size_s": config.FUNASR_BATCH_SIZE_S, "sentence_timestamp": True}
    if hotwords:
        kwargs["hotword"] = hotwords
    res = model.generate(input=str(audio), **kwargs)
    if not res:
        return {"words": [], "inexact_spans": 0}
    r = res[0]

    # 优先用逐句信息：每句单独对齐，分词规则偶尔不一致时误差只影响一句
    sentences = r.get("sentence_info")
    if sentences:
        spans = [(s.get("text", ""), s.get("timestamp", [])) for s in sentences]
    else:
        spans = [(r.get("text", ""), r.get("timestamp", []))]

    words, inexact = [], 0
    for text, stamps in spans:
        w, exact = align_tokens(text, stamps)
        if not exact:
            inexact += 1
            for x in w:
                x["inexact"] = True
        words.extend(w)
    if inexact:
        log.warning("有 %d 句文字和时间戳数量对不上，已按位置近似对齐（片段会标 low_conf）", inexact)
    return {"words": words, "inexact_spans": inexact}


def _whisper(audio: Path, device: str, hotwords: str) -> dict:
    from faster_whisper import WhisperModel

    model = WhisperModel(config.WHISPER_MODEL, device=device,
                         compute_type="float16" if device.startswith("cuda") else "int8")
    # 中文提示词让 Whisper 输出简体并带标点
    prompt = "以下是普通话的句子，使用简体中文和标点。" + (f"可能出现的词：{hotwords}。" if hotwords else "")
    segments, _ = model.transcribe(str(audio), language="zh", word_timestamps=True,
                                   initial_prompt=prompt, vad_filter=True,
                                   condition_on_previous_text=False)
    words = []
    for seg in segments:
        for w in seg.words or []:
            t = clean_whisper_word(w.word)
            if t:
                words.append({"word": t, "start": round(w.start, 3),
                              "end": round(max(w.end, w.start + 0.01), 3),
                              "prob": round(w.probability, 3)})
    return {"words": words, "inexact_spans": 0}


def run(audio: Path, device: str, backend: str = None, hotwords: str = "") -> dict:
    backend = backend or config.ASR_BACKEND
    log.info("ASR 后端: %s", backend)
    if backend == "funasr":
        out = _funasr(audio, device, hotwords)
    elif backend == "whisper":
        out = _whisper(audio, device, hotwords)
    else:
        raise ValueError(f"未知 ASR 后端: {backend}")
    out["backend"] = backend
    out["words"].sort(key=lambda w: w["start"])
    return out
