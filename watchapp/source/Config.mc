// Config: reads the server URL / token / interval.
// By design NOTHING is baked in — you enter your PulseVault Server URL and
// Ingest token in the app's settings (Garmin Connect Mobile → this app →
// Settings, or the Connect IQ simulator's App Settings). The DEFAULT_* values
// are intentionally blank so no instance/token ships in the binary.
using Toybox.Application.Properties;

(:background)
module Config {
    // Leave blank — configured per-install via app settings.
    // (Connect IQ makeWebRequest requires HTTPS; enter an https:// URL.)
    const DEFAULT_SERVER = "";
    const DEFAULT_TOKEN = "";
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

    // True once both a server URL and a token have been provided.
    function configured() {
        return serverUrl().length() > 0 && token().length() > 0;
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
