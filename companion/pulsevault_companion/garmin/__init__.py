"""Garmin BLE (GFDI) protocol — original implementation from public protocol
facts (see gadgetbridge.org/internals/specifics/garmin-protocol/).

IMPORTANT (licensing): Gadgetbridge and garmin-bridge are AGPL-3.0. This module
is written from the *documented protocol facts* (framing, message layouts, IDs),
which are not copyrightable — it does NOT copy their source. Keep it that way.

Layers (innermost last):
  Multi-Link handle byte  ->  [Multi-Link reliable]  ->  COBS frame  ->  GFDI msg
"""
