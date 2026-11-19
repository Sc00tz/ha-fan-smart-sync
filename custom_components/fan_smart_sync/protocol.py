"""Frames for Fan Smart Sync (Chungear FanMax) ceiling fans.

Pure Python with no Home Assistant imports, so it can be tested on its own.
Every frame is 13 bytes: 0x40, an 11-byte body, then a checksum. The checksum
is the sum of the 12 bytes before it, keeping the low 8 bits. 0xFF in a command
byte means "leave unchanged". See PROTOCOL.md for the full layout.
"""

from __future__ import annotations

from dataclasses import dataclass

SERVICE_UUID = "539c6813-61a0-2137-4f79-bf1a11984790"
WRITE_UUID = "539c6813-61a1-2137-4f79-bf1a11984790"  # must be written with response
NOTIFY_UUID = "539c6813-61a2-2137-4f79-bf1a11984790"

HEADER = 0x40
FRAME_LEN = 13
KIND_STATUS_REQUEST = 0xA0
KIND_COMMAND = 0xA1
KIND_STATUS = 0xB0
KIND_ACK = 0xB1

UNCHANGED = 0xFF
LIGHT_ON = 0x80
# The official app always sends 0x64 for the upper light when changing the lower one.
# Kept as-is, because those exact frames are the ones tested on a real fan.
UPPER_LIGHT_AS_APP = 0x64


def checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def frame(body: bytes) -> bytes:
    if len(body) != FRAME_LEN - 2:
        raise ValueError(f"body must be {FRAME_LEN - 2} bytes, got {len(body)}")
    data = bytes([HEADER]) + body
    return data + bytes([checksum(data)])


def status_request() -> bytes:
    return frame(bytes([KIND_STATUS_REQUEST]) + bytes(10))


def _command(fan: int = UNCHANGED, upper: int = UNCHANGED, lower: int = UNCHANGED) -> bytes:
    return frame(bytes([KIND_COMMAND, 0, 0, 0, fan, upper, lower, UNCHANGED, UNCHANGED, UNCHANGED, 0]))


def fan_command(speed: int) -> bytes:
    """Set the fan speed. 0 turns the fan off."""
    if not 0 <= speed <= 30:
        raise ValueError("speed must be 0-30")
    # The app writes the speed's decimal digits as if they were hex (10 -> 0x10).
    # For speeds 0-9 that's the same byte. It's mirrored here for fans with more speeds.
    return _command(fan=int(f"{speed:02d}", 16))


def light_command(on: bool, percent: int) -> bytes:
    """Switch the (lower) light. The fan keeps the level when it's off."""
    percent = max(0, min(100, int(percent)))
    return _command(upper=UPPER_LIGHT_AS_APP, lower=(LIGHT_ON | percent) if on else percent)


@dataclass(frozen=True)
class Status:
    version: str
    dc_motor: bool
    natural_wind: bool
    reversible: bool
    speed_count: int
    lower_light: bool
    lower_dimmable: bool
    upper_light: bool
    upper_dimmable: bool
    speed: int
    reverse: bool
    upper_on: bool
    upper_percent: int
    lower_on: bool
    lower_percent: int


class FrameError(ValueError):
    """A notification that isn't a valid frame."""


def parse(data: bytes) -> tuple[int, bytes]:
    """Check a notification and return (kind, body), where body is the 11 bytes after the header."""
    if len(data) != FRAME_LEN:
        raise FrameError(f"expected {FRAME_LEN} bytes, got {len(data)}: {data.hex()}")
    if data[0] != HEADER:
        raise FrameError(f"bad header: {data.hex()}")
    if checksum(data[:-1]) != data[-1]:
        raise FrameError(f"bad checksum: {data.hex()}")
    return data[1], bytes(data[1:-1])


def parse_status(body: bytes) -> Status:
    if body[0] != KIND_STATUS:
        raise FrameError(f"not a status reply: {body.hex()}")
    caps, lights, fan, upper, lower = body[2], body[3], body[4], body[5], body[6]
    return Status(
        version=f"{body[1] >> 4}.{body[1] & 0x0F}",
        dc_motor=bool(caps & 0x80),
        natural_wind=bool(caps & 0x40),
        reversible=bool(caps & 0x20),
        speed_count=caps & 0x1F,
        upper_dimmable=bool(lights & 0x08),
        upper_light=bool(lights & 0x04),
        lower_dimmable=bool(lights & 0x02),
        lower_light=bool(lights & 0x01),
        reverse=bool(fan & 0x80),
        speed=fan & 0x1F,
        upper_on=bool(upper & 0x80),
        upper_percent=upper & 0x7F,
        lower_on=bool(lower & 0x80),
        lower_percent=lower & 0x7F,
    )
