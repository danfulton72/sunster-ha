# Sunster HA

A focused Home Assistant custom integration for Sunster diesel heaters using the **S-A2409PRO WIFI/Bluetooth LCD controller (12/24V)** and the Sunster V2.1 encrypted BLE protocol.

## Hardware-validated

This fork was built from packet traces produced by a real S-A2409PRO controller and cross-checked against Sunster Android app 2.1.0 (`com.booyood.www.sunsterApp`). The following were exercised on the heater during development:

- AA55 wake-up and AA77 V2.1 detection
- encrypted FEAA handshake
- encrypted 47-byte CBFF status parsing
- correct OFF/ON interpretation (controller reports raw state 1 while off; 2/5/6 are ON-side states)
- power ON and OFF
- temperature mode at 21°C and 23°C
- level mode at levels 3 and 7
- set temperature while OFF, then turn ON using the pending temperature
- APK-derived time/settings synchronization
- status-before-time-sync ordering to avoid overwriting settings
- duplicate-handshake race prevention
- retry of a control command when a BLE notification is missed

## Installation

Add this repository to HACS as a custom repository of category **Integration**, install it, restart Home Assistant, then add **Sunster Diesel Heater** from Settings → Devices & services.

Manual installation: copy `custom_components/sunster_heater` to `/config/custom_components/sunster_heater` and restart Home Assistant.

## Notes

The integration intentionally focuses on functions validated on S-A2409PRO hardware. Auxiliary Sunster settings such as altitude unit, Fahrenheit mode, backlight writes and timers are not exposed yet because they were not hardware-tested in this development session.

The controller occasionally missed a BLE notification during testing. Control writes therefore retry once before being considered failed.

## Protocol

- BLE service: `FFE0`
- characteristic: `FFE1`
- V2.1 lock/beacon: `AA77`
- cleartext commands: `FE AA ...`
- status: `cmd1=00 cmd2=00`
- power: `cmd1=01`, `cmd2=01` ON / `00` OFF
- settings/time: `cmd1=03 cmd2=01`
- handshake: `cmd1=06 cmd2=00`
- encryption keys: `passwordA2409PW` and uppercase BLE MAC without separators

## Credits

Protocol work builds on the reverse-engineering in `Spettacolo83/homeassistant-diesel-heater` and was further validated against the Sunster app and S-A2409PRO hardware.
