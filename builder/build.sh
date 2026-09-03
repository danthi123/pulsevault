#!/usr/bin/env bash
# Assemble the build context (Connect IQ SDK + Fenix 7 device files + watchapp
# source + signing key — none committed) and build the pulsevault-builder image.
# Run from a machine that has the SDK installed under ~/.Garmin/ConnectIQ.
set -euo pipefail
cd "$(dirname "$0")"

CTX="$(mktemp -d)"
trap 'rm -rf "$CTX"' EXIT

SDK="$(ls -td "$HOME"/.Garmin/ConnectIQ/Sdks/*/ | head -1)"
echo "SDK: $SDK"
cp -a "$SDK" "$CTX/sdk"

# Full device library so the builder can target any supported model.
cp -a "$HOME/.Garmin/ConnectIQ/Devices" "$CTX/devices"

mkdir -p "$CTX/watchapp"
cp -a ../watchapp/source ../watchapp/resources ../watchapp/manifest.xml ../watchapp/monkey.jungle "$CTX/watchapp/"
cp -a ../watchapp/developer_key.der "$CTX/developer_key.der"
cp -a Dockerfile server.py "$CTX/"

docker build -t pulsevault-builder "$CTX"
echo "built image: pulsevault-builder"
