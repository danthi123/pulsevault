import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, WorkoutRow } from "../api";
import { fmtDistance, fmtDuration } from "../format";

const ICON: Record<string, string> = {
  running: "🏃", trail_running: "🏃", treadmill_running: "🏃",
  cycling: "🚴", road_biking: "🚴", mountain_biking: "🚴",
  swimming: "🏊", lap_swimming: "🏊", open_water_swimming: "🏊",
  hiking: "🥾", walking: "🚶", strength_training: "🏋️", cardio: "🤸",
};

export default function Workouts() {
  const { data, isLoading } = useQuery({
    queryKey: ["workouts"],
    queryFn: () => api.get<{ workouts: WorkoutRow[] }>("/api/workouts?limit=60"),
  });
  const rows = data?.workouts ?? [];

  return (
    <>
      <div className="page-title">Workouts</div>
      {isLoading ? <div className="spinner">Loading…</div> : !rows.length ? (
        <div className="card"><p className="muted">No workouts yet. Sync Garmin or upload a FIT file.</p></div>
      ) : (
        <div className="card">
          {rows.map((w) => (
            <Link to={`/workouts/${w.id}`} key={w.id} className="workout-row" style={{ color: "inherit" }}>
              <div>
                <div className="wtype">
                  {ICON[w.activity_type ?? ""] ?? "🏅"} {w.name || w.activity_type || "Activity"}
                </div>
                <div className="wsub">
                  {new Date(w.start).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div>{fmtDistance(w.distance_m)} · {fmtDuration(w.duration_s)}</div>
                <div className="wsub">
                  {w.avg_hr ? `${w.avg_hr} bpm · ` : ""}<span className="badge">{w.source === "fit_upload" ? "FIT" : "Garmin"}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
