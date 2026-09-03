#!/usr/bin/env bash
# Assemble the build context (Connect IQ SDK + full device library — neither is
# committed, both are large + licensed) and build the pulsevault-builder image.
# Run from a machine that has the SDK installed under ~/.Garmin/ConnectIQ.
#
# The image is SDK-only: the watchapp source + signing key are bind-mounted at
# runtime, so this only needs rebuilding when the SDK itself changes.
#
#   IMAGE=pulsevault-builder ./build.sh          # local tag (default)
#   IMAGE=ghcr.io/<owner>/pulsevault-builder:latest PUSH=1 ./build.sh
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="${IMAGE:-pulsevault-builder}"
CTX="$(mktemp -d)"
trap 'rm -rf "$CTX"' EXIT

SDK="$(ls -td "$HOME"/.Garmin/ConnectIQ/Sdks/*/ | head -1)"
echo "SDK: $SDK"
cp -a "$SDK" "$CTX/sdk"

# Full device library so the builder can target any supported model.
cp -a "$HOME/.Garmin/ConnectIQ/Devices" "$CTX/devices"
cp -a Dockerfile server.py "$CTX/"

docker build -t "$IMAGE" "$CTX"
echo "built image: $IMAGE"
if [ "${PUSH:-0}" = "1" ]; then
  docker push "$IMAGE"
  echo "pushed: $IMAGE"
fi
