export function fmtTime(t: number, ms = true): string {
  if (!isFinite(t)) t = 0;
  const neg = t < 0;
  t = Math.abs(t);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const pad = (n: number, w = 2) => String(n).padStart(w, "0");
  let out = (h ? `${h}:${pad(m)}` : `${m}`) + `:${pad(s)}`;
  if (ms) out += "." + pad(Math.floor((t % 1) * 1000), 3);
  return (neg ? "-" : "") + out;
}

/** 解析 "1:23.4" / "83.4" / "1:02:03" 为秒，失败返回 null */
export function parseTime(s: string): number | null {
  const parts = s.trim().split(":");
  if (!parts.length || parts.length > 3) return null;
  let t = 0;
  for (const p of parts) {
    if (!/^\d+(\.\d+)?$/.test(p)) return null;
    t = t * 60 + parseFloat(p);
  }
  return t;
}

export const round3 = (x: number) => Math.round(x * 1000) / 1000;

let counter = 0;
export function uid(prefix = "seg_u"): string {
  counter += 1;
  return `${prefix}${Date.now().toString(36)}${counter.toString(36)}${Math.random().toString(36).slice(2, 5)}`;
}

const isAlnum = (c: string) => /[A-Za-z0-9]/.test(c);

/** 拼接 token：英文/数字之间加空格，汉字之间不加（与后端 join_words 规则一致） */
export function joinWords(words: string[]): string {
  let out = "";
  for (let w of words) {
    w = w.trim();
    if (!w) continue;
    if (out) {
      const prev = out[out.length - 1];
      if ((isAlnum(prev) || ",.!?;:".includes(prev)) && isAlnum(w[0])) out += " ";
    }
    out += w;
  }
  return out;
}

export function joinTexts(a: string, b: string): string {
  if (!a) return b;
  if (!b) return a;
  return joinWords([a, b]);
}
