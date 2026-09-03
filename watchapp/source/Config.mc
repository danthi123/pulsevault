// Config: reads the server URL / token / interval.
// Values are editable in Garmin Connect Mobile (Settings for this app) via the
// app-settings below; the DEFAULT_* constants are the fallback if unset. For a
// personal sideload you can just hard-code the two DEFAULT_* values and skip the
// on-phone settings entirely.
using Toybox.Application.Properties;

(:background)
module Config {
    // NOTE: Connect IQ makeWebRequest generally requires HTTPS. Point this at
    // your PulseVault server over TLS, reachable from the phone/WiFi.
    const DEFAULT_SERVER = "https://pulsevault.local";
    const DEFAULT_TOKEN = "PASTE_INGEST_TOKEN_HERE";
    const DEFAULT_INTERVAL_MIN = 5;

    function _str(key, fallback) {
        var v = null;
        try { v = Properties.getValue(key); } catch (e) { v = null; }
        if (v != null && (v instanceof Toybox.Lang.String) && v.length() > 0) {
            return v;
        }
        return fallback;
    }

    function serverUrl() {
        var s = _str("serverUrl", DEFAULT_SERVER);
        // strip a trailing slash so we can append the path cleanly
        if (s.length() > 0 && s.substring(s.length() - 1, s.length()).equals("/")) {
            s = s.substring(0, s.length() - 1);
        }
        return s;
    }

    function token() {
        return _str("token", DEFAULT_TOKEN);
    }

    function intervalMinutes() {
        var v = DEFAULT_INTERVAL_MIN;
        try {
            var p = Properties.getValue("intervalMinutes");
            if (p != null && p instanceof Toybox.Lang.Number) { v = p; }
        } catch (e) {}
        if (v < 5) { v = 5; }  // Connect IQ background minimum is 5 minutes
        return v;
    }
}
