"""
Step 7：把各步结果合并成最终片段（纯逻辑，可单测）。

规则：
1. 重叠区间（≥ OVERLAP_MIN_S）从所有说话人区间里挖掉，单独成为 overlap 段，不给文字（需求 R4）。
2. 同一说话人间隔 ≤ MERGE_GAP_S 的区间先合并，避免碎片。
3. 每个字按「与说话人区间重叠最多」归属；落在重叠区间内的字丢弃（只留在 note 里作参考）；
   不在任何区间内的字吸附到 ATTACH_TOL_S 以内最近的区间，否则成为「无说话人」片段。
4. 长片段在句末标点处拆开；字间静音过长也拆开。
5. 没有字的说话人区间：主要被噪音事件覆盖 → non_speech；否则保留为 speech 并标 no_text。
6. 噪音事件落在空白处（无人说话）→ 独立的 non_speech 段。
"""
from typing import Dict, List, Optional

from .. import config
from .intervals import coverage, merge_intervals, overlap_length, subtract_intervals
from .textutil import ends_sentence, join_words

OVERLAP_MIN_S = 0.3     # 短于它的重叠（多是「嗯」「对」之类附和）不单独挖出来
SPLIT_GAP_S = 2.0       # 字间静音超过它就拆段
EDGE_PAD_S = 0.15       # 因静音拆段时，边界在字外留的余量
MIN_EMPTY_S = 0.3       # 没字又很短的说话人片段直接丢弃
MIN_EVENT_S = 0.5       # 空白处的噪音事件至少这么长才显示
NOISE_COVER = 0.5       # 无字片段被噪音覆盖超过该比例 → non_speech
LOW_PROB = 0.6


def _r(x: float) -> float:
    return round(float(x), 3)


def _speaker_regions(turns: List[dict], overlap_regions, gap: float) -> List[dict]:
    by_spk: Dict[str, list] = {}
    for t in turns:
        by_spk.setdefault(t["speaker"], []).append((t["start"], t["end"]))
    regions = []
    for spk, ivs in by_spk.items():
        for iv in merge_intervals(ivs, gap=gap):
            for s, e in subtract_intervals(iv, overlap_regions):
                if e - s > 0.05:
                    regions.append({"speaker": spk, "start": s, "end": e, "words": []})
    regions.sort(key=lambda r: (r["start"], r["end"]))
    return regions


def _assign_words(words, regions, overlap_regions, tol):
    """返回 (孤立字列表, 每个重叠区间内的字)。字直接追加到 region["words"]。"""
    import bisect
    starts = [r["start"] for r in regions]
    ov_words = [[] for _ in overlap_regions]
    ov_starts = [s for s, _ in overlap_regions]
    orphans = []
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        k = bisect.bisect_right(ov_starts, mid) - 1
        if k >= 0 and overlap_regions[k][0] <= mid < overlap_regions[k][1]:
            ov_words[k].append(w)
            continue
        # 候选：起点在字结束之前的区间（区间按起点排序，往前找有限个）
        hi = bisect.bisect_right(starts, w["end"] + tol)
        best, best_ov, best_dist = None, 0.0, None
        for i in range(hi - 1, -1, -1):
            r = regions[i]
            if r["end"] < w["start"] - tol - 60:   # 区间最长也就几十秒，往前看够远就停
                break
            ov = overlap_length((w["start"], w["end"]), (r["start"], r["end"]))
            if ov > best_ov:
                best, best_ov = r, ov
            elif best_ov == 0:
                dist = max(r["start"] - w["end"], w["start"] - r["end"], 0)
                if dist <= tol and (best_dist is None or dist < best_dist):
                    best, best_dist = r, dist
        if best is not None:
            best["words"].append(w)
        else:
            orphans.append(w)
    for r in regions:
        r["words"].sort(key=lambda w: w["start"])
    return orphans, ov_words


def _split_region(r: dict, max_len: float) -> List[dict]:
    """按静音和句末标点拆分，返回若干 {start,end,words}。"""
    words = r["words"]
    if not words:
        return [r]
    groups, cur = [], [words[0]]
    for prev, w in zip(words, words[1:]):
        gap = w["start"] - prev["end"]
        too_long = (prev["end"] - cur[0]["start"]) >= max_len and ends_sentence(prev["word"])
        if gap > SPLIT_GAP_S or too_long:
            groups.append(cur)
            cur = []
        cur.append(w)
    groups.append(cur)
    if len(groups) == 1:
        start = min(r["start"], words[0]["start"])
        end = max(r["end"], words[-1]["end"])
        return [{**r, "start": start, "end": end}]

    out = []
    for i, g in enumerate(groups):
        if i == 0:
            start = min(r["start"], g[0]["start"])
        else:
            prev_end = groups[i - 1][-1]["end"]
            gap = g[0]["start"] - prev_end
            start = g[0]["start"] - EDGE_PAD_S if gap > SPLIT_GAP_S else (prev_end + g[0]["start"]) / 2
        if i == len(groups) - 1:
            end = max(r["end"], g[-1]["end"])
        else:
            nxt = groups[i + 1][0]["start"]
            gap = nxt - g[-1]["end"]
            end = g[-1]["end"] + EDGE_PAD_S if gap > SPLIT_GAP_S else (g[-1]["end"] + nxt) / 2
        out.append({**r, "start": start, "end": end, "words": g})
    return out


def _event_label(span, events) -> Optional[str]:
    """该区间内覆盖时长最多的事件标签。"""
    acc: Dict[str, float] = {}
    for e in events:
        ov = overlap_length(span, (e["start"], e["end"]))
        if ov > 0:
            acc[e["label"]] = acc.get(e["label"], 0) + ov
    return max(acc, key=acc.get) if acc else None


def merge(duration: float, turns: List[dict], overlaps: List[list], words: List[dict],
          vad: List[list], events: List[dict]) -> List[dict]:
    overlap_regions = [iv for iv in merge_intervals(overlaps, gap=0.1) if iv[1] - iv[0] >= OVERLAP_MIN_S]
    vad_regions = merge_intervals(vad)
    event_regions = merge_intervals([(e["start"], e["end"]) for e in events])

    regions = _speaker_regions(turns, overlap_regions, config.MERGE_GAP_S)
    orphans, ov_words = _assign_words(words, regions, overlap_regions, config.ATTACH_TOL_S)

    segs: List[dict] = []

    # 说话人片段
    for r in regions:
        for piece in _split_region(r, config.MAX_SEGMENT_S):
            segs.append(_make_speech(piece, vad_regions, event_regions, events))

    # 无说话人的字：连续的字归成一段
    if orphans:
        group = [orphans[0]]
        for w in orphans[1:] + [None]:
            if w is not None and w["start"] - group[-1]["end"] <= config.MERGE_GAP_S * 2:
                group.append(w)
                continue
            seg = _make_speech({"speaker": None, "start": group[0]["start"], "end": group[-1]["end"],
                                "words": group}, vad_regions, event_regions, events)
            seg["flags"].append("no_speaker")
            segs.append(seg)
            if w is not None:
                group = [w]

    # 重叠片段
    for (s, e), ws in zip(overlap_regions, ov_words):
        spk = sorted({t["speaker"] for t in turns if overlap_length((s, e), (t["start"], t["end"])) > 0})
        segs.append({"start": s, "end": e, "type": "overlap", "speaker": None, "overlap_speakers": spk,
                     "text": "", "words": [], "confidence": None,
                     "note": ("ASR参考(不可靠): " + join_words([w["word"] for w in ws])) if ws else "",
                     "flags": []})

    segs = [s for s in segs if s is not None]

    # 空白处的噪音事件
    occupied = merge_intervals([(s["start"], s["end"]) for s in segs])
    by_label: Dict[str, list] = {}
    for e in events:
        by_label.setdefault(e["label"], []).append((e["start"], e["end"]))
    for label, ivs in by_label.items():
        for iv in merge_intervals(ivs, gap=0.5):
            for s, e in subtract_intervals(iv, occupied):
                if e - s >= MIN_EVENT_S:
                    segs.append({"start": s, "end": e, "type": "non_speech", "speaker": None,
                                 "overlap_speakers": [], "text": "", "words": [], "confidence": None,
                                 "note": label, "flags": []})

    segs.sort(key=lambda s: (s["start"], s["end"]))
    out = []
    for i, s in enumerate(segs):
        s["start"] = _r(max(0.0, s["start"]))
        s["end"] = _r(min(duration, s["end"]) if duration else s["end"])
        if s["end"] - s["start"] < 0.01:
            continue
        s["id"] = f"seg_{len(out) + 1:05d}"
        s["reviewed"] = False
        s["words"] = [{k: v for k, v in w.items() if k in ("word", "start", "end", "prob")} for w in s["words"]]
        out.append(s)
    return out


def _make_speech(piece, vad_regions, event_regions, events) -> Optional[dict]:
    span = (piece["start"], piece["end"])
    dur = span[1] - span[0]
    ws = piece["words"]
    flags = []
    if not ws:
        if dur < MIN_EMPTY_S:
            return None
        if coverage(span, event_regions) >= NOISE_COVER:
            return {"start": span[0], "end": span[1], "type": "non_speech", "speaker": None,
                    "overlap_speakers": [], "text": "", "words": [], "confidence": None,
                    "note": _event_label(span, events) or "噪音", "flags": []}
        flags.append("no_text")

    probs = [w["prob"] for w in ws if w.get("prob") is not None]
    conf = round(sum(probs) / len(probs), 3) if probs else None
    if (conf is not None and conf < LOW_PROB) or any(w.get("inexact") for w in ws):
        flags.append("low_conf")
    if dur < config.SHORT_SEGMENT_S:
        flags.append("short")
    if vad_regions and coverage(span, vad_regions) < config.LOW_VAD_RATIO:
        flags.append("low_vad")
    if ws and coverage(span, event_regions) > 0.3:
        flags.append("noise")
    return {"start": span[0], "end": span[1], "type": "speech", "speaker": piece["speaker"],
            "overlap_speakers": [], "text": join_words([w["word"] for w in ws]), "words": ws,
            "confidence": conf, "note": "", "flags": flags}
