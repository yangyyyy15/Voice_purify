"""
文本工具（纯 Python，可单测）：
- FunASR 输出的带标点文本和逐 token 时间戳对齐
- 中英混排拼接
"""
import re
import unicodedata
from typing import List, Optional

SENT_END = set("。！？!?；;…")


def is_punct(ch: str) -> bool:
    return unicodedata.category(ch).startswith("P") or ch in "～~·"


def is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0x20000 <= cp <= 0x2A6DF
            or 0xF900 <= cp <= 0xFAFF or 0x3040 <= cp <= 0x30FF)


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*|\S")


def tokenize_with_punct(text: str) -> List[str]:
    """
    按 FunASR 的 token 粒度切分：每个汉字一个 token，连续英文/数字一个 token。
    标点不算 token，附着到前一个 token 末尾（句首标点附到后一个）。
    """
    tokens: List[str] = []
    pending = ""
    for m in _TOKEN_RE.finditer(text):
        t = m.group()
        if len(t) == 1 and is_punct(t):
            if tokens:
                tokens[-1] += t
            else:
                pending += t
            continue
        tokens.append(pending + t if pending else t)
        pending = ""
    return tokens


def align_tokens(text: str, timestamps: List[List[float]], ms: bool = True) -> (List[dict], bool):
    """
    把文本 token 和时间戳一一对应。返回 (words, exact)。
    数量对不上时（不同版本 FunASR 分词规则有差异），按位置线性映射，exact=False 供上层打标。
    """
    tokens = tokenize_with_punct(text)
    k = 1000.0 if ms else 1.0
    stamps = [(float(s) / k, float(e) / k) for s, e in timestamps]
    if not tokens or not stamps:
        return [], not tokens and not stamps
    n, m = len(tokens), len(stamps)
    exact = n == m
    words = []
    for i, tok in enumerate(tokens):
        if exact:
            s, e = stamps[i]
        else:
            # token i 覆盖时间戳 [lo, hi]
            lo = int(i * m / n)
            hi = max(lo, int((i + 1) * m / n) - 1)
            s, e = stamps[lo][0], stamps[min(hi, m - 1)][1]
        words.append({"word": tok, "start": round(s, 3), "end": round(max(e, s + 0.01), 3)})
    return words, exact


def _core(tok: str) -> str:
    return "".join(c for c in tok if not is_punct(c))


def join_words(words: List[str]) -> str:
    """拼接 token：英文/数字之间补空格，汉字之间不加。"""
    out = ""
    for w in words:
        w = w.strip()
        if not w:
            continue
        if out:
            prev = _core(out[-8:])[-1:] if _core(out[-8:]) else out[-1]
            first = w[0]
            if prev.isascii() and prev.isalnum() and first.isascii() and first.isalnum():
                out += " "
            elif out[-1] in ",.!?;:" and first.isascii() and first.isalnum():
                out += " "
        out += w
    return out


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok[-1] in SENT_END


def clean_whisper_word(w: str) -> Optional[str]:
    w = w.strip()
    return w or None
