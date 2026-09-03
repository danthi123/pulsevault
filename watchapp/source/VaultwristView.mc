// Minimal foreground view. On show it pushes current metrics immediately and
// displays the result — the quickest way to confirm the app reaches your server.
using Toybox.WatchUi;
using Toybox.Graphics;
using Toybox.Communications;
using Toybox.Time;

class VaultwristView extends WatchUi.View {

    var _status = "Opening...";
    var _cursors = null;

    function initialize() {
        View.initialize();
    }

    function onShow() {
        _push();
    }

    function _push() {
        if (!Config.configured()) {
            _status = "Set URL + token\nin app settings";
            WatchUi.requestUpdate();
            return;
        }
        _status = "Syncing...";
        WatchUi.requestUpdate();

        var res = Collector.collect();
        _cursors = res["cursors"];
        var url = Config.serverUrl() + "/api/ingest/metrics";
        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_POST,
            :headers => {
                "Content-Type" => Communications.REQUEST_CONTENT_TYPE_JSON,
                "Authorization" => "Bearer " + Config.token()
            },
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };
        Communications.makeWebRequest(url, res["payload"], options, method(:onResp));
    }

    function onResp(responseCode as Toybox.Lang.Number, data as Toybox.Lang.Dictionary or Toybox.Lang.String or Toybox.PersistedContent.Iterator or Null) as Void {
        if (responseCode == 200) {
            if (_cursors != null) { Collector.commit(_cursors); }
            _status = "Synced OK";
        } else {
            _status = "HTTP " + responseCode;
        }
        WatchUi.requestUpdate();
    }

    // "5m ago" / "2h ago" / "3d ago" / "never" — so a phone-free user can see at
    // a glance whether wireless sync is actually reaching the server.
    function _lastSync() {
        var ts = Collector.lastPushTs();
        if (ts == 0) { return "never"; }
        var age = Time.now().value() - ts;
        if (age < 90) { return "just now"; }
        if (age < 3600) { return (age / 60) + "m ago"; }
        if (age < 86400) { return (age / 3600) + "h ago"; }
        return (age / 86400) + "d ago";
    }

    function onUpdate(dc) {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();
        var cx = dc.getWidth() / 2;
        var cy = dc.getHeight() / 2;
        dc.drawText(cx, cy - 46, Graphics.FONT_MEDIUM, "Vaultwrist", Graphics.TEXT_JUSTIFY_CENTER);
        dc.drawText(cx, cy - 10, Graphics.FONT_SMALL, _status, Graphics.TEXT_JUSTIFY_CENTER);
        dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, cy + 20, Graphics.FONT_XTINY, "Last sync: " + _lastSync(), Graphics.TEXT_JUSTIFY_CENTER);
        dc.drawText(cx, cy + 42, Graphics.FONT_XTINY, "Queued: " + Collector.queued(), Graphics.TEXT_JUSTIFY_CENTER);
    }
}
