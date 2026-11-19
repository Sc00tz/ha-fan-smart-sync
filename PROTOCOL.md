# Fan Smart Sync: Bluetooth protocol

Worked out from the Fan Smart Sync 1.1 Android app (package `com.satellite.fansmartsync`, built on
Chungear's "FanMax" app with an Ideabus BLE library), then checked against a real fan.

Each claim is marked **[seen]** (observed on the real fan, 2026-11-18) or **[code]** (read from the
app, not yet tried).

## Connection

- The app has Bluetooth permissions and no internet permission, so there is no cloud. **[code]**
- The fan advertises the name `Fan` padded with spaces, plus service `539C6813-61A0-…`. The app lists
  any device whose name starts with `Fan`. **[seen]**
- There's no pairing, bonding or key. You connect, enable notifications and write. **[seen]**
- Service `539C6813-61A0-2137-4F79-BF1A11984790`:
  - write `…61A1…` must be written **with response**. Writes without response are silently ignored. **[seen]**
  - notify `…61A2…` carries the replies. **[seen]**
- A second service, `539C6813-0AD0-…`, has two write/notify characteristics. The app doesn't use it
  (it's probably the BLE module's own configuration), so leave it alone. **[seen]**
- Only one phone or hub can be connected at a time. Close the app before another client connects.

## Frames

Each frame is 13 bytes: `40`, an 11-byte body, then a checksum. **[code]**, **[seen]**

- The checksum is the sum of all 12 preceding bytes (header included), keeping the low 8 bits.
- `FF` in a body byte means "leave unchanged".
- The app sends a command at most every 200 ms and polls status once a second.

| Body byte | Status request | Command (`A1`) | Status reply (`B0`) |
|---|---|---|---|
| 0 | `A0` | `A1` | `B0` |
| 1 | 00 | 00 | firmware version, as nibbles (`10` = v1.0) |
| 2 | 00 | 00 | capabilities: bit7 DC motor, bit6 natural wind, bit5 reversible, bits 0-4 number of speeds |
| 3 | 00 | 00 | light and timer capabilities: bit1 lower light dimmable, bit0 lower light fitted (bits 7-2 cover the timers and the upper light) |
| 4 | 00 | fan speed: `00` off, `01`-`03` | current fan: bit7 reverse, bit6 natural wind, bits 0-4 speed (0 = off) |
| 5 | 00 | upper light (the app always sends `64`) | upper light: bit7 on, bits 0-6 % |
| 6 | 00 | lower light: bit7 on, bits 0-6 % | lower light: bit7 on, bits 0-6 % |
| 7-9 | 00 | timers (see below), otherwise `FF` | remaining fan and light timer minutes |
| 10 | 00 | 00 | security and delay flags |

The fan answers a command with `B1` and a status request with `B0`. **[code]**

## Ready-made frames

| Action | Bytes to write |
|---|---|
| Read status | `40A000000000000000000000E0` **[seen]** |
| Fan off | `40A100000000FFFFFFFFFF00DC` **[seen]** |
| Fan speed 1 | `40A100000001FFFFFFFFFF00DD` **[seen]** |
| Fan speed 2 | `40A100000002FFFFFFFFFF00DE` **[seen]** |
| Fan speed 3 | `40A100000003FFFFFFFFFF00DF` **[seen]** |
| Light on, 100% | `40A1000000FF64E4FFFFFF0025` **[seen]** |
| Light on, 30% | `40A1000000FF649EFFFFFF00DF` **[seen]** |
| Light on, 50% | `40A1000000FF64B2FFFFFF00F3` |
| Light off (keeps the level) | `40A1000000FF6464FFFFFF00A5` **[seen]** |

For other light levels, byte 6 is `0x80 + percent` for on and `percent` for off.

On 2026-11-18, every **[seen]** command was answered with `B1` within about 50 ms, and the next
status read showed the new state. A fan command leaves the light alone, and a light command leaves
the fan alone, because unchanged bytes are sent as `FF`. **[seen]**

## Example status (read 2026-11-18) **[seen]**

The reply was `40 B0 10 23 A3 00 00 33 00 00 00 22 1B`, and its checksum is correct.

- **Firmware:** v1.0.
- **Motor:** AC (not DC), 3 speeds, reversible, no natural-wind mode.
- **Light:** the lower light is fitted and dimmable.
- **At the time:** the fan was off, and the light was off with its level kept at 51%.

## Not supported by the app

- **Reverse:** the fan reports it can reverse and shows the current direction (byte 4, bit 7), but the
  app has no button for it. Setting bit 7 in a command might work, but that's untested.
- **Speeds:** speeds are written as a decimal number read as hex (a bug for 10 or more). This doesn't
  matter for a 3-speed fan.

## Timers [code]

The fan has its own sleep timer for the fan and its own light timer, in minutes (11 bits each):

- **Fan sleep timer:** bytes 7-9 are `S[7:0]`, `L[3:0] 0 S[10:8]`, `0 L[10:4]`.
- **Light timer:** packed the same way, with the other timer's current value kept in place.

Home Assistant automations can replace both, so they aren't needed for basic control.
