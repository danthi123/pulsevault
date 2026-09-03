// Background service: fires on the temporal schedule (>= 5 min), collects recent
// metrics, and POSTs them to the server. Web requests relay through the phone's
// Garmin Connect Mobile connection (or WiFi where available), so this keeps
// working while your watch stays paired to your iPhone.
using Toybox.System;
using Toybox.Background;
using Toybox.Communications;

(:background)
class VaultwristBackground extends System.ServiceDelegate {

    var _cursors = null;

    function initialize() {
        ServiceDelegate.initialize();
    }

    function onTemporalEvent() {
        if (!Config.configured()) {
            Background.exit(0);  // nothing to send until the user configures it
            return;
        }
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
        // Advance cursors only on success, so a failed/offline push retries later.
        if (responseCode == 200 && _cursors != null) {
            Collector.commit(_cursors);
        }
        Background.exit(responseCode);
    }
}
