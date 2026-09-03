// Collector: reads recent samples from SensorHistory + ActivityMonitor and
// builds the JSON payload the server expects at /api/ingest/metrics.
//
// SensorHistory exposes rolling buffers of the Garmin-proprietary wellness
// metrics (stress, Body Battery) that FIT/Apple Health don't reliably give —
// this is the whole point of the on-watch app.
using Toybox.SensorHistory;
using Toybox.ActivityMonitor;
using Toybox.Lang;

(:background)
module Collector {

    // Up to this many recent samples per metric per push.
    const MAX_SAMPLES = 120;

    function collect() {
        var metrics = {};
        metrics["heart_rate"]   = _read(:getHeartRateHistory);
        metrics["stress"]       = _read(:getStressHistory);
        metrics["body_battery"] = _read(:getBodyBatteryHistory);
        metrics["spo2"]         = _read(:getOxygenSaturationHistory);
        metrics["respiration"]  = _read(:getRespirationRateHistory);

        var today = {};
        if (ActivityMonitor has :getInfo) {
            var info = ActivityMonitor.getInfo();
            if (info != null) {
                if (info.steps != null)    { today["steps"] = info.steps; }
                if (info.calories != null) { today["calories"] = info.calories; }
                // ActivityMonitor distance is in centimeters.
                if (info.distance != null) { today["distance_m"] = info.distance / 100.0; }
            }
        }

        return { "device" => "fenix7", "metrics" => metrics, "today" => today };
    }

    // Generic reader: dynamically calls the SensorHistory getter named by `sym`
    // if the device supports it, returning [[epochSeconds, value], ...].
    function _read(sym) {
        var out = [];
        if (!(SensorHistory has sym)) { return out; }

        var iter = null;
        try {
            var m = new Lang.Method(SensorHistory, sym);
            iter = m.invoke({ :period => MAX_SAMPLES, :order => SensorHistory.ORDER_NEWEST_FIRST });
        } catch (e) {
            return out;
        }
        if (iter == null) { return out; }

        var s = iter.next();
        var n = 0;
        while (s != null && n < MAX_SAMPLES) {
            if (s.data != null && s.when != null) {
                out.add([ s.when.value(), s.data ]);  // when.value() = UNIX epoch seconds
            }
            s = iter.next();
            n += 1;
        }
        return out;
    }
}
