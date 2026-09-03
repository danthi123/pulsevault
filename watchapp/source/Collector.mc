// Collector: reads recent samples from SensorHistory + ActivityMonitor and
// maintains a PERSISTENT on-watch outbox so data survives long offline gaps.
//
// The problem it solves: SensorHistory only retains a rolling window (a few
// hours). If the watch can't reach the server for longer than that window, the
// un-sent samples roll off the buffer and are lost forever. So instead of
// reading-and-sending directly, every sync first CAPTURES any new samples into
// the app's own Storage (an outbox that persists across background runs and
// reboots), then DRAINS the oldest queued samples to the server. Uploads only
// remove what the server confirmed (HTTP 200), so a failed/offline push just
// leaves the backlog in place to retry. The backlog is bounded per metric
// (oldest dropped when full), so worst case we lose only the very oldest data
// after being offline for a very long time — never the recent stuff.
//
// Note: this covers the live SensorHistory metrics only (HR / stress / Body
// Battery / SpO2 / respiration). Connect IQ has no API for the watch's computed
// SLEEP data, so sleep can never come from here — it comes from Garmin Connect.
using Toybox.SensorHistory;
using Toybox.ActivityMonitor;
using Toybox.Application.Storage;
using Toybox.Lang;
using Toybox.Time;

(:background)
module Collector {

    // Samples sent per metric per push (background RAM is tight). After a gap,
    // successive 5-min syncs drain the rest of the backlog in chunks.
    const MAX_PER_METRIC = 96;
    // Persistent backlog cap per metric. At typical SensorHistory cadence this
    // covers many hours offline. Oldest pairs are dropped past this. Lower it if
    // a low-memory device struggles; the Fenix 7 has ample headroom.
    const MAX_OUTBOX = 240;
    // How far back to ask the buffer for (seconds); the device returns only what
    // it still holds. The capture cursor keeps us from re-capturing.
    const WINDOW_SECONDS = 86400;

    // metric name -> SensorHistory accessor selector.
    function _metricList() {
        return [
            ["heart_rate", :getHeartRateHistory],
            ["stress", :getStressHistory],
            ["body_battery", :getBodyBatteryHistory],
            ["spo2", :getOxygenSaturationHistory],
            ["respiration", :getRespirationRateHistory],
        ];
    }

    // Capture new samples into the outbox, then build a payload from the OLDEST
    // queued samples. Returns:
    //   { "payload" => {device, metrics, today}, "cursors" => {metric=>drainCount} }
    // "cursors" is the drain plan: how many oldest outbox pairs each metric put
    // into this payload, removed by commit() only after a confirmed push.
    function collect() {
        var list = _metricList();
        for (var i = 0; i < list.size(); i++) {
            _capture(list[i][0], list[i][1]);
        }

        var metrics = {};
        var plan = {};
        for (var i = 0; i < list.size(); i++) {
            var name = list[i][0];
            var ob = _loadOutbox(name);
            var n = ob.size() / 2;
            var take = n < MAX_PER_METRIC ? n : MAX_PER_METRIC;
            var arr = [];
            for (var j = 0; j < take; j++) {
                arr.add([ob[j * 2], ob[j * 2 + 1]]);
            }
            metrics[name] = arr;
            plan[name] = take;
        }

        var today = {};
        if (ActivityMonitor has :getInfo) {
            var info = ActivityMonitor.getInfo();
            if (info != null) {
                if (info.steps != null) { today["steps"] = info.steps; }
                if (info.calories != null) { today["calories"] = info.calories; }
                if (info.distance != null) { today["distance_m"] = info.distance / 100.0; }
            }
        }
        return {
            "payload" => { "device" => "garmin", "metrics" => metrics, "today" => today },
            "cursors" => plan,
        };
    }

    // Remove the drained (oldest) samples from each metric's outbox after a 200.
    function commit(plan) {
        var keys = plan.keys();
        for (var i = 0; i < keys.size(); i++) {
            var name = keys[i];
            var take = plan[name];
            if (take == null || take <= 0) { continue; }
            var ob = _loadOutbox(name);
            var drop = take * 2;
            if (drop >= ob.size()) {
                ob = [];
            } else {
                ob = ob.slice(drop, ob.size());
            }
            Storage.setValue("ob_" + name, ob);
        }
    }

    // ---- internals ----

    function _loadOutbox(name) {
        var v = Storage.getValue("ob_" + name);
        if (v != null && v instanceof Lang.Array) { return v; }
        return [];
    }

    // Append SensorHistory samples newer than the capture cursor to the outbox.
    // Reads NEWEST-first and stops at the cursor (or MAX_OUTBOX), so the work is
    // bounded even on the very first run when the whole window is "new".
    function _capture(name, sym) {
        if (!(SensorHistory has sym)) { return; }

        var cap = 0;
        var cv = Storage.getValue("cap_" + name);
        if (cv != null && cv instanceof Lang.Number) { cap = cv; }

        var iter = null;
        try {
            var m = new Lang.Method(SensorHistory, sym);
            iter = m.invoke({
                :period => new Time.Duration(WINDOW_SECONDS),
                :order => SensorHistory.ORDER_NEWEST_FIRST,
            });
        } catch (e) {
            return;
        }
        if (iter == null) { return; }

        // Collect new samples newest-first (bounded), tracking the newest ts.
        var fresh = [];
        var maxT = cap;
        var count = 0;
        var s = iter.next();
        while (s != null && count < MAX_OUTBOX) {
            if (s.when != null) {
                var t = s.when.value();  // UNIX epoch seconds
                if (t <= cap) { break; } // reached already-captured region
                if (s.data != null) {
                    fresh.add(t);
                    fresh.add(s.data);
                    if (t > maxT) { maxT = t; }
                    count++;
                }
            }
            s = iter.next();
        }
        if (fresh.size() == 0) { return; }

        // Reverse to oldest-first and append (all newer than everything already
        // queued, since t > cap >= the previous capture's max).
        var ob = _loadOutbox(name);
        for (var k = fresh.size() - 2; k >= 0; k -= 2) {
            ob.add(fresh[k]);
            ob.add(fresh[k + 1]);
        }

        // Bound the backlog: drop oldest pairs past the cap.
        var maxLen = MAX_OUTBOX * 2;
        if (ob.size() > maxLen) {
            ob = ob.slice(ob.size() - maxLen, ob.size());
        }

        Storage.setValue("ob_" + name, ob);
        if (maxT > cap) { Storage.setValue("cap_" + name, maxT); }
    }
}
