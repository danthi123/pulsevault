// Collector: reads recent samples from SensorHistory + ActivityMonitor and
// builds the JSON payload for /api/ingest/metrics — designed to capture as much
// data as possible without wasting battery/data.
//
// Strategy: per-metric "last-sent" cursors are persisted in Storage. Each sync
// pulls the buffer OLDEST-first (a wide ~24h window), keeps only samples newer
// than the cursor, up to a memory-safe cap, and returns cursors to advance ONLY
// after a successful (HTTP 200) push. So normal syncs send just new samples, and
// after being offline we drain each buffer forward in chunks over successive
// syncs — never skipping, never duplicating (the server also dedupes by ts).
using Toybox.SensorHistory;
using Toybox.ActivityMonitor;
using Toybox.Application.Storage;
using Toybox.Lang;
using Toybox.Time;

(:background)
module Collector {

    // Memory-safe cap per metric per push (background RAM is tight). After a gap,
    // successive 5-min syncs drain the rest.
    const MAX_PER_METRIC = 96;
    // How far back to ask the buffer for (seconds). The device returns only what
    // it still holds; the cursor keeps us from re-sending.
    const WINDOW_SECONDS = 86400;

    // Returns { "payload" => {device, metrics, today}, "cursors" => {metric=>maxEpoch} }.
    function collect() {
        var metrics = {};
        var cursors = {};
        _read(metrics, cursors, "heart_rate", :getHeartRateHistory);
        _read(metrics, cursors, "stress", :getStressHistory);
        _read(metrics, cursors, "body_battery", :getBodyBatteryHistory);
        _read(metrics, cursors, "spo2", :getOxygenSaturationHistory);
        _read(metrics, cursors, "respiration", :getRespirationRateHistory);

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
            "cursors" => cursors,
        };
    }

    // Advance the per-metric cursors after a confirmed push. Call from onResp(200).
    function commit(cursors) {
        var keys = cursors.keys();
        for (var i = 0; i < keys.size(); i++) {
            var k = keys[i];
            Storage.setValue("sent_" + k, cursors[k]);
        }
    }

    function _read(metrics, cursors, name, sym) {
        var out = [];
        if (!(SensorHistory has sym)) { metrics[name] = out; return; }

        var sent = 0;
        var v = Storage.getValue("sent_" + name);
        if (v != null && v instanceof Lang.Number) { sent = v; }

        var iter = null;
        try {
            var m = new Lang.Method(SensorHistory, sym);
            iter = m.invoke({
                :period => new Time.Duration(WINDOW_SECONDS),
                :order => SensorHistory.ORDER_OLDEST_FIRST,
            });
        } catch (e) {
            metrics[name] = out;
            return;
        }
        if (iter == null) { metrics[name] = out; return; }

        var maxTs = sent;
        var s = iter.next();
        while (s != null && out.size() < MAX_PER_METRIC) {
            if (s.data != null && s.when != null) {
                var t = s.when.value();  // UNIX epoch seconds
                if (t > sent) {
                    out.add([t, s.data]);
                    if (t > maxTs) { maxTs = t; }
                }
            }
            s = iter.next();
        }
        metrics[name] = out;
        cursors[name] = maxTs;
    }
}
