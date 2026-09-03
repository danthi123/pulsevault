import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, SleepRow } from "../api";
import { fmtDuration, hhmm, todayISO } from "../format";
import DayNav from "../components/DayNav";

interface StageSeg { start: string; end: string; stage: string }
interface SleepResp { session: SleepRow | null; stages: StageSeg[] }

const STAGE_COLOR: Record<string, string> = {
  deep: "var(--sleep-deep)", light: "var(--sleep-light)",
  rem: "var(--sleep-rem)", awake: "var(--sleep-awake)", unmeasured: "#455a64",
};

export default function Sleep() {
  const [day, setDay] = useState(todayISO());
  const { data, isLoading } = useQuery({
    queryKey: ["sleep", day],
    queryFn: () => api.get<SleepResp>(`/api/sleep?day=${day}`),
  });
  const s = data?.session;

  return (
    <>
      <div className="page-title">Sleep</div>
      <DayNav day={day} setDay={setDay} />
      {isLoading ? <div className="spinner">Loading…</div> : !s ? (
        <div className="card"><p className="muted">No sleep recorded for this night.</p></div>
      ) : (
        <>
          <div className="tiles">
            <Tile label="Total sleep" value={fmtDuration(s.total_s)} />
            <Tile label="Score" value={s.score ?? "—"} />
            <Tile label="Bedtime" value={hhmm(s.start)} />
            <Tile label="Wake" value={hhmm(s.end)} />
          </div>

          <div className="card">
            <h3>Stages</h3>
            <CompositionBar s={s} />
            <div className="legend" style={{ marginTop: 10 }}>
              <span style={{ ["--dot" as any]: 0 }}><i style={dot("deep")} />Deep {fmtDuration(s.deep_s)}</span>
              <span><i style={dot("light")} />Light {fmtDuration(s.light_s)}</span>
              <span><i style={dot("rem")} />REM {fmtDuration(s.rem_s)}</span>
              <span><i style={dot("awake")} />Awake {fmtDuration(s.awake_s)}</span>
            </div>
          </div>

          {data?.stages.length ? (
            <div className="card">
              <h3>Hypnogram</h3>
              <Hypnogram stages={data.stages} />
            </div>
          ) : null}
        </>
      )}
    </>
  );
}

function dot(stage: string): React.CSSProperties {
  return { display: "inline-block", width: 10, height: 10, borderRadius: 3,
    background: STAGE_COLOR[stage], marginRight: 5 };
}

function CompositionBar({ s }: { s: SleepRow }) {
  const parts = [
    { k: "deep", v: s.deep_s ?? 0 }, { k: "light", v: s.light_s ?? 0 },
    { k: "rem", v: s.rem_s ?? 0 }, { k: "awake", v: s.awake_s ?? 0 },
  ];
  const total = parts.reduce((a, p) => a + p.v, 0) || 1;
  return (
    <div className="sleep-bar">
      {parts.map((p) => (
        <div key={p.k} title={`${p.k} ${fmtDuration(p.v)}`}
          style={{ width: `${(p.v / total) * 100}%`, background: STAGE_COLOR[p.k] }} />
      ))}
    </div>
  );
}

function Hypnogram({ stages }: { stages: StageSeg[] }) {
  const level: Record<string, number> = { awake: 3, rem: 2, light: 1, deep: 0, unmeasured: 1 };
  const t0 = Date.parse(stages[0].start);
  const t1 = Date.parse(stages[stages.length - 1].end);
  const span = t1 - t0 || 1;
  const H = 120;
  return (
    <svg width="100%" height={H} viewBox={`0 0 1000 ${H}`} preserveAspectRatio="none">
      {stages.map((seg, i) => {
        const x = ((Date.parse(seg.start) - t0) / span) * 1000;
        const w = ((Date.parse(seg.end) - Date.parse(seg.start)) / span) * 1000;
        const lvl = level[seg.stage] ?? 1;
        const y = 10 + (3 - lvl) * ((H - 30) / 3);
        return <rect key={i} x={x} y={y} width={Math.max(w, 1)} height={(H - 20) / 4}
          fill={STAGE_COLOR[seg.stage]} rx={2} />;
      })}
    </svg>
  );
}

function Tile({ label, value }: { label: string; value: any }) {
  return <div className="tile"><div className="label">{label}</div><div className="value">{value}</div></div>;
}
