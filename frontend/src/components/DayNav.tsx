import { addDaysISO, prettyDay, todayISO } from "../format";

export default function DayNav({ day, setDay }: { day: string; setDay: (d: string) => void }) {
  const isToday = day >= todayISO();
  return (
    <div className="day-nav">
      <button onClick={() => setDay(addDaysISO(day, -1))} aria-label="Previous day">‹</button>
      <div className="day-label">{prettyDay(day)}</div>
      <button onClick={() => setDay(addDaysISO(day, 1))} disabled={isToday} aria-label="Next day">›</button>
      <input
        type="date"
        value={day}
        max={todayISO()}
        onChange={(e) => e.target.value && setDay(e.target.value)}
      />
    </div>
  );
}
