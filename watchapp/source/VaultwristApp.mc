// App entry point. Schedules the periodic background push and provides the
// foreground view (which also does an immediate push when you open the app —
// handy for testing).
using Toybox.Application;
using Toybox.Background;
using Toybox.Time;
using Toybox.System;

(:background)
class VaultwristApp extends Application.AppBase {

    function initialize() {
        AppBase.initialize();
    }

    function onStart(state) {
        _scheduleBackground();
    }

    function _scheduleBackground() {
        if (!(Toybox has :Background)) { return; }
        var mins = Config.intervalMinutes();
        try {
            Background.registerForTemporalEvent(new Time.Duration(mins * 60));
        } catch (e) {
            System.println("temporal event register failed: " + e.getErrorMessage());
        }
    }

    function getInitialView() {
        return [ new VaultwristView() ];
    }

    // Returning the ServiceDelegate makes onTemporalEvent fire in the background.
    function getServiceDelegate() {
        return [ new VaultwristBackground() ];
    }

    function onBackgroundData(data) {
        // Foreground notification of the last background result; unused for now.
    }
}
