"""Unit tests for the Garmin GFDI protocol codec layers.

Run:  python -m tests.test_protocol   (from the companion/ dir)
No pytest required — plain asserts + a summary. These verify internal
consistency and standard-algorithm check values; byte-exactness against a real
Fenix must still be confirmed with a packet capture.
"""
from __future__ import annotations

from pulsevault_companion.garmin import cobs, gfdi, mlink
from pulsevault_companion.garmin.crc import crc16


def test_crc_known_vector():
    assert crc16(b"123456789") == 0xBB3D, "CRC-16/ARC check value"
    # Seeded CRC == feeding two halves sequentially.
    assert crc16(b"56789", seed=crc16(b"1234")) == crc16(b"123456789")


def test_cobs_roundtrip():
    cases = [
        b"",
        b"hello",
        b"\x00",
        b"\x00\x00\x00",
        b"\x01\x00\x02\x00\x03",
        b"ends-with-zero\x00",
        bytes(range(256)),
        b"\x11" * 300,          # forces a 0xFF code split (>254 run)
        b"\x00" * 300,
    ]
    for data in cases:
        assert cobs.cobs_decode(cobs.cobs_encode(data)) == data, data[:8]
        assert cobs.decode_frame(cobs.encode_frame(data)) == data, data[:8]


def test_frame_reassembler_split():
    payloads = [b"\x01\x02\x03", b"\x00abc\x00", b"z"]
    stream = b"".join(cobs.encode_frame(p) for p in payloads)
    # Feed the stream in awkward 3-byte chunks across frame boundaries.
    r = cobs.FrameReassembler()
    got = []
    for i in range(0, len(stream), 3):
        got.extend(r.feed(stream[i : i + 3]))
    assert got == payloads, got


def test_gfdi_roundtrip():
    payload = b"\xde\xad\xbe\xef\x00\x11"
    wire = gfdi.encode(gfdi.Msg.DEVICE_INFORMATION, payload, seq=3)
    msg = gfdi.decode(wire)
    assert msg.msg_id == gfdi.Msg.DEVICE_INFORMATION
    assert msg.seq == 3
    assert msg.payload == payload
    # length field self-consistency
    assert wire[0] | (wire[1] << 8) == len(wire)


def test_gfdi_crc_rejected():
    wire = bytearray(gfdi.encode(gfdi.Msg.SYSTEM_EVENT, b"\x01\x02"))
    wire[4] ^= 0xFF  # corrupt a payload byte
    try:
        gfdi.decode(bytes(wire))
    except ValueError as e:
        assert "CRC" in str(e)
    else:
        raise AssertionError("expected CRC mismatch")


def test_mlink_control_frames():
    reg = mlink.register_service(mlink.Service.GFDI, reliable=False)
    assert reg[0] == mlink.CONTROL_HANDLE
    assert reg[1] == mlink.RequestType.REGISTER_ML_REQ
    assert len(reg) == 13
    # client id (8 LE) then service (2 LE) then reliable byte
    assert reg[2:10] == (mlink.GADGETBRIDGE_CLIENT_ID).to_bytes(8, "little")
    assert reg[10:12] == (mlink.Service.GFDI).to_bytes(2, "little")
    assert reg[12] == 0

    ca = mlink.close_all()
    assert ca[1] == mlink.RequestType.CLOSE_ALL_REQ

    resp = (mlink.Service.GFDI).to_bytes(2, "little") + bytes([0, 5, 1])
    parsed = mlink.parse_register_response(resp)
    assert parsed == {"service": 1, "status": 0, "handle": 5, "reliable": True}

    assert mlink.frame_gfdi(5, b"\xaa\xbb")[0] == 5
    assert mlink.is_mlr(b"\x80\x00") is True
    assert mlink.is_mlr(b"\x05\x00") is False


def test_uuids():
    assert mlink.ML_SERVICE_UUID.startswith("6a4e2800")
    assert mlink.NOTIFY_UUID.startswith("6a4e2810")
    assert mlink.WRITE_UUID.startswith("6a4e2820")


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} protocol tests passed")


if __name__ == "__main__":
    _run()
