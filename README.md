# Fan Smart Sync for Home Assistant

Control ceiling fans that use the **Fan Smart Sync** phone app from Home Assistant, directly over
Bluetooth. There's no cloud and no account. These fans use a Chungear "FanMax" Bluetooth module.

Each fan becomes one device with:

- **a fan entity**: off and each of the fan's speeds (3 on most models), set from a slider or by percentage.
- **a light entity**: on/off and brightness, if the fan has a dimmable light.

Changes made with the wall remote or the phone app show up within 30 seconds.

## Install

1. In HACS, open **⋮ > Custom repositories**, add `https://github.com/Sc00tz/ha-fan-smart-sync`, and
   choose the category **Integration**.
2. Install **Fan Smart Sync** and restart Home Assistant.
3. Close the Fan Smart Sync app on your phone. The fan accepts one Bluetooth connection at a time.
4. The fan should appear under **Settings > Devices & services** as discovered. Otherwise, choose
   **Add integration > Fan Smart Sync** and pick it from the list.

Without HACS, copy `custom_components/fan_smart_sync` into your Home Assistant `config/custom_components/`
folder and restart.

## Requirements

- **Bluetooth:** Home Assistant needs a Bluetooth adapter in range of the fan, or an
  [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html) near it.
- **One connection at a time:** the fan only accepts one Bluetooth connection. Home Assistant
  connects for each status check or command, and disconnects after 15 idle seconds. Between checks,
  the phone app can still connect. While the app holds the connection, Home Assistant marks the fan
  unavailable until the app lets go.

## Not supported

- **Reverse:** the fan reports whether it can reverse, but the official app has no reverse control,
  so neither does this integration.
- **Built-in timers:** the fan's own sleep and light timers aren't exposed. Use Home Assistant
  automations instead.

## How it works

The fan takes 13-byte commands on a Bluetooth characteristic and replies with its full status. The
details, including a ready-made frame for every action, are in [PROTOCOL.md](PROTOCOL.md).

Not affiliated with Chungear, Satellite or the makers of the Fan Smart Sync app.
