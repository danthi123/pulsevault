export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}
export function addDaysISO(iso: string, delta: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + delta);
  return d.toISOString().slice(0, 10);
}
export function prettyDay(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  const today = todayISO();
  if (iso === today) return "Today";
  if (iso === addDaysISO(today, -1)) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}
export function hhmm(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}
export function fmtDuration(seconds: number | null | undefined): string {
  if (!seconds && seconds !== 0) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}
export function fmtDistance(meters: number | null | undefined): string {
  if (!meters && meters !== 0) return "—";
  if (meters >= 1000) return `${(meters / 1000).toFixed(2)} km`;
  return `${Math.round(meters)} m`;
}
export function fmtNum(n: number | null | undefined): string {
  return n === null || n === undefined ? "—" : n.toLocaleString();
}
export function fmtPace(avgSpeedMs: number | null | undefined): string {
  if (!avgSpeedMs) return "—";
  const totalSec = Math.round(1000 / avgSpeedMs);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${s.toString().padStart(2, "0")} /km`;
}
