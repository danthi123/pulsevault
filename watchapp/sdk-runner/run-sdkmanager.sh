#!/usr/bin/env bash
# Launch Garmin's Connect IQ SDK Manager GUI inside the ciq-sdkmanager container
# (Ubuntu 22.04 with the EOL webkit-4.0 libs that Arch/CachyOS no longer ships),
# rendering to your desktop. Downloads land in your real ~/.Garmin so the host
# toolchain (monkeyc) can use them afterward.
#
# Usage:  ./run-sdkmanager.sh
# Then: sign in with your Garmin account, download the latest SDK, and add the
# "fenix 7" device under the Devices tab.
set -euo pipefail

IMG=ciq-sdkmanager
SDKMGR="$HOME/Applications/connectiq-sdk-manager/bin/sdkmanager"

[ -x "$SDKMGR" ] || { echo "SDK Manager not found at $SDKMGR" >&2; exit 1; }
[ -n "${XAUTHORITY:-}" ] && [ -f "$XAUTHORITY" ] || {
    echo "XAUTHORITY not set/found — are you in a graphical session?" >&2; exit 1; }
mkdir -p "$HOME/.Garmin"

# Verified working combo on KDE/Plasma Wayland (XWayland :0):
#   --ipc=host        -> fixes MIT-SHM BadAccess for the GTK/WebKit UI
#   --hostname host   -> makes the mounted X cookie's FamilyLocal entry match
#   XAUTHORITY cookie -> passes X auth without needing xhost/xauth on the host
exec docker run --rm -it \
    --user "$(id -u):$(id -g)" \
    --hostname "$(cat /etc/hostname)" \
    --ipc=host \
    -e HOME="$HOME" \
    -e DISPLAY="${DISPLAY:-:0}" \
    -e XDG_RUNTIME_DIR=/tmp \
    -e XAUTHORITY=/tmp/.xauth \
    -e LIBGL_ALWAYS_SOFTWARE=1 \
    -e WEBKIT_DISABLE_COMPOSITING_MODE=1 \
    -e NO_AT_BRIDGE=1 \
    -v "$XAUTHORITY:/tmp/.xauth:ro" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v "$HOME:$HOME" \
    "$IMG" "$SDKMGR"
