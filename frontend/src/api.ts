// Thin fetch wrapper. Cookies (the session) are sent automatically same-origin.

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: opts.body && !(opts.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : undefined,
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(p: string) => req<T>(p),
  post: <T>(p: string, body?: unknown) =>
    req<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  postForm: <T>(p: string, form: FormData) =>
    req<T>(p, { method: "POST", body: form }),
};

// ---- shared types ----
export interface DailyRow {
  day: string; steps: number | null; steps_goal: number | null;
  distance_m: number | null; active_seconds: number | null; floors: number | null;
  calories: number | null; resting_hr: number | null; min_hr: number | null;
  max_hr: number | null; avg_stress: number | null; body_battery_high: number | null;
  body_battery_low: number | null; intensity_minutes: number | null;
  vo2max: number | null; training_status: string | null;
}
export interface SleepRow {
  start: string; end: string; deep_s: number | null; light_s: number | null;
  rem_s: number | null; awake_s: number | null; total_s: number | null; score: number | null;
}
export interface SeriesPoint { t: string; v: number }
export interface WorkoutRow {
  id: number; name: string | null; activity_type: string | null; source: string | null;
  start: string; end: string | null; duration_s: number | null; distance_m: number | null;
  calories: number | null; avg_hr: number | null; max_hr: number | null;
  avg_speed: number | null; ascent_m: number | null;
}
