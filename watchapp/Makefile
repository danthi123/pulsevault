# Build/run helpers for the Vaultwrist Connect IQ app.
# Requires the Connect IQ SDK's bin/ on your PATH (monkeyc, monkeydo, connectiq).
# See README.md for SDK install.

DEVICE ?= fenix7
KEY    ?= developer_key.der
OUT    ?= bin/Vaultwrist.prg
JUNGLE ?= monkey.jungle

# Auto-resolve SDK tools: prefer PATH, else the newest installed SDK.
MONKEYC ?= $(shell command -v monkeyc 2>/dev/null || ls -td $(HOME)/.Garmin/ConnectIQ/Sdks/*/bin/monkeyc 2>/dev/null | head -1)
MONKEYDO ?= $(shell command -v monkeydo 2>/dev/null || ls -td $(HOME)/.Garmin/ConnectIQ/Sdks/*/bin/monkeydo 2>/dev/null | head -1)
CONNECTIQ ?= $(shell command -v connectiq 2>/dev/null || ls -td $(HOME)/.Garmin/ConnectIQ/Sdks/*/bin/connectiq 2>/dev/null | head -1)

# Where the watch mounts (MTP). Override if your gvfs path differs:
#   make sideload WATCH=/run/user/1000/gvfs/mtp:host=.../Primary
WATCH ?=

.PHONY: build run clean sideload check

build:
	@mkdir -p bin
	$(MONKEYC) -d $(DEVICE) -f $(JUNGLE) -o $(OUT) -y $(KEY) -w
	@echo "built $(OUT)"

# Launch the simulator (run once in another terminal), then load the app onto it.
run: build
	$(MONKEYDO) $(OUT) $(DEVICE)

# Start the Connect IQ simulator GUI.
sim:
	$(CONNECTIQ)

# Build the store/sideload-wireless export package (.iq) for all devices in the
# manifest. Upload this at apps.garmin.com/developer/dashboard (unlisted app),
# then install to the watch wirelessly from Garmin Connect Mobile.
package:
	@mkdir -p bin
	$(MONKEYC) -e -f $(JUNGLE) -o bin/Vaultwrist.iq -y $(KEY) -w
	@echo "built bin/Vaultwrist.iq"

# Copy the built .prg onto a mounted watch (set WATCH=... to its GARMIN parent).
sideload: build
	@test -n "$(WATCH)" || (echo "set WATCH=<path to the watch mount containing GARMIN/>"; exit 1)
	cp $(OUT) "$(WATCH)/GARMIN/Apps/"
	@echo "copied to $(WATCH)/GARMIN/Apps/ — unplug and open the app on the watch"

check:
	@test -n "$(MONKEYC)" && echo "monkeyc: $(MONKEYC)" || echo "monkeyc NOT found — install the SDK"
	@test -f $(KEY) && echo "key: $(KEY) present" || echo "key missing — run: make key"

key: developer_key.der
developer_key.der:
	openssl genrsa -out developer_key.pem 4096
	openssl pkcs8 -topk8 -inform PEM -outform DER -in developer_key.pem -out developer_key.der -nocrypt

clean:
	rm -rf bin
