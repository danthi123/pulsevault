"""Command-line entry point for the companion agent."""
from __future__ import annotations

import argparse
import json
import logging
import sys

from . import __version__, config
from .agent import Agent


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pulsevault-companion",
                                     description="PulseVault desktop companion agent")
    parser.add_argument("-c", "--config", help="path to config.toml")
    parser.add_argument("--version", action="version", version=f"pulsevault-companion {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("run", help="run continuously, syncing on an interval (default)")
    sub.add_parser("once", help="scan and sync a single time, then exit")
    sub.add_parser("status", help="show config and which sources currently see the watch")
    p_probe = sub.add_parser("ble-probe", help="[experimental] dump the watch's BLE GATT table")
    p_probe.add_argument("--address", help="BLE MAC/UUID to target directly")

    args = parser.parse_args(argv)
    cfg = config.load(args.config)
    _setup_logging(cfg.log_level)

    cmd = args.cmd or "run"

    if cmd == "ble-probe":
        from .sources.ble import BleSource
        spec = {"type": "ble", "enabled": True}
        if getattr(args, "address", None):
            spec["address"] = args.address
        result = BleSource(spec).probe()
        print(json.dumps(result, indent=2))
        return 0

    if not cfg.token:
        print("ERROR: no ingest token set. Copy it from the web UI (Settings → Device Sync) "
              "into config.toml or the PV_TOKEN env var.", file=sys.stderr)
        return 2

    agent = Agent(cfg)

    if cmd == "status":
        from . import inbox
        print(f"server:   {cfg.server_url}")
        print(f"interval: {cfg.poll_interval}s")
        print(f"inbox:    {agent.fit_dir}  ({len(inbox.fit_files(agent.fit_dir))} .fit waiting)")
        print(f"state:    {cfg.resolved_state_file()}")
        if agent.puller is not None:
            try:
                seen = agent.puller.available()
            except Exception as exc:  # noqa: BLE001
                seen = f"error: {exc}"
            print(f"auto-pull ({agent.puller.name}): {'watch detected' if seen is True else seen}")
        else:
            print("auto-pull: off")
        return 0

    if cmd == "once":
        pulled, uploaded = agent.cycle()
        print(f"pulled {pulled}, uploaded {uploaded}")
        return 0

    agent.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
