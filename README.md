# Sunster HA

A focused Home Assistant custom integration for Sunster diesel heaters using the **S-A2409PRO WIFI/Bluetooth LCD controller (12/24V)** and the Sunster V2.1 encrypted BLE protocol.

## Hardware-validated

This integration was built from packet traces produced by a real S-A2409PRO controller and cross-checked against Sunster Android app 2.1.0 (`com.booyood.www.sunsterApp`). The V2.1 protocol layout and settings writes are aligned with the application bundle.

Validated/control paths include:

- Bluetooth auto-discovery via the advertised FFE0 service
- AA55 wake-up and AA77 V2.1 detection
- encrypted FEAA handshake
- encrypted status parsing
- OFF/ON interpretation (raw state 1 is off; 2/5/6 are ON-side states)
- power ON/OFF
- temperature mode
- level mode
- controller-supported operating modes derived from mainboard/key-mode capabilities
- set temperature while OFF, then turn ON using the pending temperature
- APK-compatible time/settings synchronization
- capability-aware settings writes that preserve unsupported fields
- response-command matching so unrelated BLE notifications do not acknowledge a write
- retry of a control command when a BLE notification is missed

## Exposed Home Assistant controls and diagnostics

Where supported by the controller, the integration exposes:

- Climate power, current temperature and target temperature
- Heater level 1-10
- Operating mode
- Temperature and altitude units
- Voice language (limited to languages advertised by the controller)
- Controller backlight
- Temperature compensation
- Start and stop temperature offsets
- Controller Wi-Fi switch
- Auto Start/Stop switch
- Ambient and heater temperatures
- Supply voltage, altitude and CO
- Current level and remaining runtime
- Run state/step, fault details, mainboard type and hardware version diagnostics
- Estimated fuel consumption rate (L/h) and total fuel used (L)

The integration is capability-driven. V2.1 uses `0xFF` and capability nibbles for unavailable settings; unsupported controls are unavailable and their raw values are preserved when other settings are written.

## Fuel consumption

The controller does not report fuel flow, so the integration estimates it. Each heater level is a fixed fuel-pump pulse rate, so the rate is interpolated linearly between the consumption at level 1 and at level 10, using the level the heater is actually running at (in temperature mode this follows the controller's automatic level changes).

- **Fuel Consumption Rate** (L/h) reads 0 when the heater is off, disconnected or in ventilation mode.
- **Fuel Used** (L) is a running total that survives restarts. It is a `total_increasing` volume sensor, so it works with Utility Meter helpers (daily/monthly), statistics and cost templates.

The defaults are the rated **0.16–0.45 L/h** of the Sunster 2 kW split heater (SH B2 / A2200BS). For another heater, or to calibrate, open **Settings → Devices & services → Sunster Diesel Heater → Configure** and set the level 1 and level 10 rates. A simple calibration: brim the tank, run for a few days, refill and measure, then multiply both rates by *measured litres ÷ Fuel Used increase*.

Limitations: glow-plug ignition and cooldown are treated like normal running at the reported level, high-altitude pump trimming is not modelled, and gaps of more than five minutes without a status update (Home Assistant restart, Bluetooth dropout) are not counted.

### Heaters without a fuel tank

Fuel tank and pump-model fields are decoded so their capability state is preserved, but this integration does **not** expose tank-volume or pump-model entities. A controller that reports these fields as unsupported (`0xFF`) therefore works without any fuel-tank assumptions, and changing unrelated settings will continue to send the unsupported values back unchanged.

## Installation

Add this repository to HACS as a custom repository of category **Integration**, install it, and restart Home Assistant. With the heater powered on and in Bluetooth range, Home Assistant should automatically discover **Sunster Diesel Heater** and offer a setup notification. Select it and enter the controller PIN (default `1234`).

You can also go to **Settings → Devices & services → Add Integration → Sunster Diesel Heater**. The setup flow performs an active Bluetooth scan and presents discovered heaters in a picker; you do not need to know or type the Bluetooth address.

Manual installation: copy `custom_components/sunster_heater` to `/config/custom_components/sunster_heater` and restart Home Assistant. Bluetooth discovery works the same way after restart.

## Debug logging

For hardware validation, enable integration debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.sunster_heater: debug
```

Restart Home Assistant after changing the logger configuration. Debug output records decrypted controller status frames, parsed values, command IDs, acknowledgements and retry/timeout information. The configured PIN is never logged, handshake payloads are redacted, and the MAC field returned by the controller-info packet is redacted.

The Controller Wi-Fi entity is disabled by default because changing that setting can change how the controller connects. Enable that entity manually only when deliberately testing Wi-Fi behavior.

## Protocol

- BLE service: `FFE0`
- characteristic: `FFE1`
- V2.1 lock/beacon: `AA77`
- cleartext frame header: `FE AA`
- status: `cmd1=00 cmd2=00`
- device capability/MAC data: `cmd1=00 cmd2=03`
- power/settings: `cmd1=01`
- timers: `cmd1=02`
- settings/time: `cmd1=03 cmd2=01`
- handshake: `cmd1=06 cmd2=00`
- V2.1 responses use `cmd1 + 0x80`
- encryption keys: `passwordA2409PW` and uppercase BLE MAC without separators

## Tests

Protocol tests cover the V2.1 status field layout, no-tank capability handling, settings preservation and APK-compatible time synchronization. CI also checks that the Bluetooth discovery flow and FFE0 manifest matcher remain present.

## Credits

Protocol work builds on the reverse-engineering in `Spettacolo83/homeassistant-diesel-heater` and was further validated against the Sunster app and S-A2409PRO hardware.
