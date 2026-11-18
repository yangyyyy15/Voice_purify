"""
区间运算工具。区间统一用 (start, end) 元组，单位秒，start < end。
"""
from typing import Iterable, List, Tuple

Interval = Tuple[float, float]


def merge_intervals(intervals: Iterable[Interval], gap: float = 0.0) -> List[Interval]:
    """合并重叠或间隔不超过 gap 的区间，返回排好序的结果。"""
    items = sorted((float(s), float(e)) for s, e in intervals if e > s)
    out: List[Interval] = []
    for s, e in items:
        if out and s <= out[-1][1] + gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def subtract_intervals(base: Interval, holes: List[Interval]) -> List[Interval]:
    """从 base 中挖掉 holes（holes 需已 merge_intervals）。"""
    s, e = base
    out: List[Interval] = []
    cur = s
    for hs, he in holes:
        if he <= cur:
            continue
        if hs >= e:
            break
        if hs > cur:
            out.append((cur, hs))
        cur = max(cur, he)
        if cur >= e:
            break
    if cur < e:
        out.append((cur, e))
    return out


def overlap_length(a: Interval, b: Interval) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def coverage(target: Interval, intervals: List[Interval]) -> float:
    """intervals（需已合并）覆盖 target 的比例，0~1。"""
    dur = target[1] - target[0]
    if dur <= 0:
        return 0.0
    return sum(overlap_length(target, iv) for iv in intervals) / dur


def contains_point(intervals: List[Interval], t: float) -> bool:
    """t 是否落在任一区间内（intervals 需已合并排序）。"""
    import bisect
    i = bisect.bisect_right([s for s, _ in intervals], t) - 1
    return i >= 0 and intervals[i][0] <= t < intervals[i][1]
