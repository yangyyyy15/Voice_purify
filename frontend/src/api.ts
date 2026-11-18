import type { Project, ProjectSummary } from "./types";

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const body = await r.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* 非 JSON 响应 */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  list: () => req<ProjectSummary[]>("/api/projects"),
  get: (id: string) => req<Project>(`/api/projects/${encodeURIComponent(id)}`),
  save: (p: Project) =>
    req<{ ok: boolean; saved_at: string }>(`/api/projects/${encodeURIComponent(p.video_id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(p),
    }),
  peaks: (id: string) => req<{ rate: number; data: number[] }>(`/api/projects/${encodeURIComponent(id)}/peaks`),
  mediaUrl: (id: string) => `/api/projects/${encodeURIComponent(id)}/media`,
};
