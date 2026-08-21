# Sunster HA

A focused Home Assistant custom integration for Sunster diesel heaters using the **S-A2409PRO WIFI/Bluetooth LCD controller (12/24V)** and the Sunster V2.1 encrypted BLE protocol.

## Hardware-validated

This integration was built from packet traces produced by a real S-A2409PRO controller and cross-checked against Sunster Android app 2.1.0 (`com.booyood.www.sunsterApp`). The V2.1 protocol layout and settings writes are aligned with the application bundle.

Validated/control paths include:

- AA55 wake-up and AA77 V2.1 detection
- encrypted FEAA handshake
- encrypted V2.1 status parsing
- OFF/ON interpretation (raw state 1 is off; 2/5/6 are ON-side states)
- power ON/OFF
- temperature and level modes
- controller-supported modes from mainboard/key-mode capabilities
- APK-compatible time/settings synchronization
- capability-aware writes that preserve unsupported values
- response-command matching so unrelated BLE notifications do not acknowledge a write
- retry of a control command when a BLE notification is missed

## Home Assistant entities

Where the controller advertises support, the integration exposes climate power/current/target temperature, heater level, operating mode, temperature and altitude units, voice language, backlight, temperature compensation, start/stop temperature offsets, controller Wi-Fi, Auto Start/Stop, ambient/heater temperatures, supply voltage, altitude, CO, current level, remaining runtime, fault data, protocol/mainboard data and firmware diagnostics.

### Heaters without a fuel tank

V2.1 reports unavailable settings using `0xFF` and capability nibbles. Fuel-tank and pump-model bytes are decoded and preserved, but no tank or pump-model entities are created. On a controller without a fuel tank, changing another setting therefore keeps the unsupported fuel fields at `0xFF` instead of writing an invented tank configuration.

## Installation

Add this repository to HACS as a custom repository of category **Integration**, install it, restart Home Assistant, then add **Sunster Diesel Heater** from Settings → Devices & services.

Manual installation: copy `custom_components/sunster_heater` to `/config/custom_components/sunster_heater` and restart Home Assistant.

## Protocol

- BLE service: `FFE0`
- characteristic: `FFE1`
- V2.1 lock/beacon: `AA77`
- cleartext frame header: `FE AA`
- status: `cmd1=00 cmd2=00`
- capability/MAC data: `cmd1=00 cmd2=03`
- power/settings: `cmd1=01`
- timers: `cmd1=02`
- settings/time: `cmd1=03 cmd2=01`
- handshake: `cmd1=06 cmd2=00`
- V2.1 responses use `cmd1 + 0x80`
- encryption keys: `passwordA2409PW` and uppercase BLE MAC without separators

## Credits

Protocol work builds on the reverse-engineering in `Spettacolo83/homeassistant-diesel-heater` and was further validated against the Sunster app and S-A2409PRO hardware.
