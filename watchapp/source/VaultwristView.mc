// Minimal foreground view. On show it pushes current metrics immediately and
// displays the result — the quickest way to confirm the app reaches your server.
using Toybox.WatchUi;
using Toybox.Graphics;
using Toybox.Communications;

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

    function onUpdate(dc) {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();
        var cx = dc.getWidth() / 2;
        var cy = dc.getHeight() / 2;
        dc.drawText(cx, cy - 24, Graphics.FONT_MEDIUM, "Vaultwrist", Graphics.TEXT_JUSTIFY_CENTER);
        dc.drawText(cx, cy + 16, Graphics.FONT_SMALL, _status, Graphics.TEXT_JUSTIFY_CENTER);
    }
}
