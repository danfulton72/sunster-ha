from __future__ import annotations
from datetime import datetime
from typing import Any

SUNSTER_KEY = b"passwordA2409PW"
UNSUPPORTED = 0xFF


def _xor_repeat(data: bytes | bytearray, key: bytes) -> bytearray:
    return bytearray(b ^ key[i % len(key)] for i, b in enumerate(data))


def _u16(lo: int, hi: int) -> int:
    return lo | (hi << 8)


def _i16(lo: int, hi: int) -> int:
    value = _u16(lo, hi)
    return value - 0x10000 if value >= 0x8000 else value


def _i8(value: int) -> int:
    return value - 0x100 if value > 0x7F else value


def _unit_value(raw: int) -> tuple[int, bool]:
    """Decode the V2.1 capability/value nibble used by unit settings."""
    return raw & 0x0F, ((raw >> 4) & 0x0F) != 0x0F


class SunsterProtocol:
    """Sunster S-A2409PRO / V2.1 FEAA+CBFF protocol."""

    def __init__(self, mac: str) -> None:
        self.device_key = mac.replace(":", "").replace("-", "").upper().encode()
        self.v21 = False
        self.last_mode = 1
        self.last_param = 5
        self.is_on = False
        self.settings: dict[str, Any] = {}

    def encrypt(self, packet: bytes | bytearray) -> bytearray:
        return _xor_repeat(_xor_repeat(packet, SUNSTER_KEY), self.device_key)

    def decrypt(self, packet: bytes | bytearray) -> bytearray:
        return _xor_repeat(_xor_repeat(packet, SUNSTER_KEY), self.device_key)

    @staticmethod
    def wakeup(pin: int) -> bytearray:
        hi, lo = divmod(pin, 100)
        pkt = bytearray([0xAA, 0x55, hi & 0xFF, lo & 0xFF, 0x01, 0x00, 0x00, 0])
        pkt[7] = sum(pkt[2:7]) & 0xFF
        return pkt

    @staticmethod
    def _feaa(cmd1: int, cmd2: int, payload: bytes = b"") -> bytearray:
        total = 9 + len(payload)
        pkt = bytearray([0xFE, 0xAA, 0, 0, total & 0xFF, (total >> 8) & 0xFF, cmd1, cmd2])
        pkt.extend(payload)
        pkt.append(sum(pkt) & 0xFF)
        return pkt

    def _wrap(self, pkt: bytearray) -> bytearray:
        return self.encrypt(pkt) if self.v21 else pkt

    def handshake(self, pin: int) -> bytearray:
        payload = bytes([pin % 100, pin // 100])
        return self.encrypt(self._feaa(0x06, 0x00, payload))

    def status(self) -> bytearray:
        return self._wrap(self._feaa(0x00, 0x00))

    def device_info(self) -> bytearray:
        return self._wrap(self._feaa(0x00, 0x03))

    def command_key(self, packet: bytes | bytearray) -> tuple[int, int] | None:
        raw = self.decrypt(packet) if self.v21 else bytearray(packet)
        if len(raw) < 8 or raw[0:2] != b"\xFE\xAA":
            return None
        return raw[6], raw[7]

    def power(self, on: bool) -> bytearray:
        payload = bytes([self.last_mode, self.last_param, 0xFF, 0xFF])
        return self._wrap(self._feaa(0x01, 0x01 if on else 0x00, payload))

    def set_temperature(self, temp: int) -> bytearray:
        self.last_mode = 2
        self.last_param = temp
        payload = bytes([2, temp & 0xFF, 0xFF, 0xFF])
        return self._wrap(self._feaa(0x01, 0x01 if self.is_on else 0x00, payload))

    def set_level(self, level: int) -> bytearray:
        self.last_mode = 1
        self.last_param = level
        payload = bytes([1, level & 0xFF, 0xFF, 0xFF])
        return self._wrap(self._feaa(0x01, 0x01 if self.is_on else 0x00, payload))

    def set_mode(self, mode: int) -> bytearray:
        if mode in (1, 3, 4):
            param = self.last_param if self.last_mode in (1, 3, 4) else 5
        else:
            param = self.last_param if self.last_mode == 2 else 21
        self.last_mode = mode
        self.last_param = param
        payload = bytes([mode, param, 0xFF, 0xFF])
        return self._wrap(self._feaa(0x01, 0x01 if self.is_on else 0x00, payload))

    def _setting(self, name: str, default: int) -> int:
        value = self.settings.get(name, default)
        if isinstance(value, bool):
            value = int(value)
        return int(default if value is None else value) & 0xFF

    def _settings_payload(self, *, current_time: int = 0, date: datetime | None = None) -> bytes:
        if date is not None:
            temp_comp = date.year & 0xFF
            language = date.month
            oil_volume = date.day
            pump_model = (date.weekday() + 1) % 7
        else:
            temp_comp = self._setting("temp_comp", 0)
            language = self._setting("broadcast_language", UNSUPPORTED)
            oil_volume = self._setting("oil_volume", UNSUPPORTED)
            pump_model = self._setting("pump_model", UNSUPPORTED)
        return bytes([
            self._setting("altitude_unit_raw", 0),
            self._setting("temp_unit_raw", 0),
            current_time & 0xFF, (current_time >> 8) & 0xFF,
            temp_comp, language, oil_volume, pump_model,
            self._setting("back_light", UNSUPPORTED),
            self._setting("startup_temp_difference", UNSUPPORTED),
            self._setting("shutdown_temp_difference", UNSUPPORTED),
            self._setting("wifi", UNSUPPORTED),
            self._setting("i_stop", UNSUPPORTED),
        ])

    def time_sync(self, dt: datetime) -> bytearray:
        minutes = 0x8000 | (dt.hour * 60 + dt.minute)
        return self._wrap(self._feaa(0x03, 0x01, self._settings_payload(current_time=minutes, date=dt)))

    def update_settings(self, **changes: int | bool) -> bytearray:
        for key, value in changes.items():
            if key == "temp_unit":
                self.settings["temp_unit_raw"] = int(value) & 0x0F
            elif key == "altitude_unit":
                self.settings["altitude_unit_raw"] = int(value) & 0x0F
            else:
                self.settings[key] = int(value) & 0xFF
        return self._wrap(self._feaa(0x03, 0x01, self._settings_payload()))

    @staticmethod
    def modes_for_mainboard(mainboard_type: int) -> tuple[int, ...]:
        return {
            0: (1, 2),
            1: (1, 2, 3, 4),
            10: (1, 2, 4),
            11: (1, 2, 3),
            20: (1, 2),
            21: (1, 2, 3),
        }.get(mainboard_type, (1, 2))

    def parse_notification(self, data: bytearray) -> dict[str, Any] | None:
        if len(data) >= 2 and data[0:2] == b"\xAA\x77":
            self.v21 = True
            return {"aa77": True}
        if len(data) < 8:
            return None
        raw = self.decrypt(data) if self.v21 else bytearray(data)
        if len(raw) < 8:
            return None

        response_cmd = (raw[6] - 0x80, raw[7]) if 0x80 <= raw[6] <= 0x86 else None
        if response_cmd == (0, 3):
            if len(raw) < 27:
                return {"_response_cmd": response_cmd}
            language_markers = _u16(raw[16], raw[17])
            language_options = [0] + [bit + 1 for bit in range(7) if language_markers & (1 << bit)]
            key_mode = raw[26]
            result: dict[str, Any] = {
                "_response_cmd": response_cmd,
                "product_part_number": f"{int.from_bytes(raw[8:12], 'little'):08x}",
                "device_hardware_version": _u16(raw[12], raw[13]),
                "device_software_version": _u16(raw[14], raw[15]),
                "language_markers": language_markers,
                "language_options": tuple(language_options),
                "chip_type": _u16(raw[24], raw[25]),
                "key_mode": key_mode,
            }
            if key_mode & 0x80:
                modes = tuple(mode for bit, mode in enumerate((1, 2, 3, 4)) if key_mode & (1 << bit))
                if modes:
                    result["available_modes"] = modes
            return result

        if len(raw) < 46:
            return {"_response_cmd": response_cmd} if response_cmd else None
        protocol_version = raw[2]
        mainboard_type = raw[8]
        run_state, run_mode, run_param = raw[10], raw[11], raw[12]
        now_gear, run_step = raw[13], raw[14]
        fault_display, fault_code = raw[15], raw[16]
        temp_unit, supports_temp_unit = _unit_value(raw[17])
        altitude_unit, supports_altitude_unit = _unit_value(raw[20])
        on = run_state in (2, 5, 6)

        parsed: dict[str, Any] = {
            "connected": True,
            "_response_cmd": response_cmd,
            "protocol_version": protocol_version,
            "mainboard_type": mainboard_type,
            "available_modes": self.modes_for_mainboard(mainboard_type),
            "raw_run_state": run_state,
            "running_state": 1 if on else 0,
            "running_mode": run_mode if run_mode in (1, 2, 3, 4) else 0,
            "running_step": run_step,
            "current_level": now_gear,
            "fault_display": fault_display,
            "fault_code": fault_code,
            "error_code": fault_display if fault_code >= 128 else (fault_display & 0x3F),
            "fault_type": ("XMZ", "TY", "DD1", "DD2")[(fault_display >> 6) & 0x03],
            "temp_unit": temp_unit,
            "supports_temp_unit": supports_temp_unit,
            "ambient_temperature": _i16(raw[18], raw[19]),
            "altitude_unit": altitude_unit,
            "supports_altitude_unit": supports_altitude_unit,
            "altitude": _u16(raw[21], raw[22]),
            "voltage": _u16(raw[23], raw[24]) / 10,
            "heater_temperature": _i16(raw[25], raw[26]) / 10,
            "co": _u16(raw[27], raw[28]) / 10,
            "power_field": raw[29],
            "hardware_version": _u16(raw[30], raw[31]),
            "software_version": _u16(raw[32], raw[33]),
            "temp_comp": _i8(raw[34]),
            "broadcast_language": raw[35],
            "supports_language": raw[35] != UNSUPPORTED,
            "supports_fuel_tank": raw[36] != UNSUPPORTED,
            "supports_pump_model": raw[37] != UNSUPPORTED,
            "back_light": None if raw[38] == UNSUPPORTED else raw[38],
            "supports_back_light": raw[38] != UNSUPPORTED,
            "startup_temp_difference": None if raw[39] == UNSUPPORTED else raw[39],
            "supports_startup_temp_difference": raw[39] != UNSUPPORTED,
            "shutdown_temp_difference": None if raw[40] == UNSUPPORTED else raw[40],
            "supports_shutdown_temp_difference": raw[40] != UNSUPPORTED,
            "wifi_enabled": None if raw[41] == UNSUPPORTED else bool(raw[41]),
            "supports_wifi": raw[41] != UNSUPPORTED,
            "auto_start_stop": None if raw[42] == UNSUPPORTED else bool(raw[42]),
            "supports_auto_start_stop": raw[42] != UNSUPPORTED,
            "heater_mode": raw[43],
            "remaining_runtime": None if _u16(raw[44], raw[45]) == 0xFFFF else _u16(raw[44], raw[45]),
            "supports_remaining_runtime": _u16(raw[44], raw[45]) != 0xFFFF,
        }

        if run_mode in (1, 3, 4):
            parsed["set_level"] = max(1, min(10, run_param))
        elif run_mode == 2:
            parsed["set_temp"] = run_param
            parsed["set_level"] = max(1, min(10, now_gear))

        self.is_on = on
        if on and run_mode in (1, 2, 3, 4):
            self.last_mode = run_mode
            self.last_param = run_param

        self.settings.update({
            "altitude_unit_raw": raw[20],
            "temp_unit_raw": raw[17],
            "temp_comp": raw[34],
            "broadcast_language": raw[35],
            "oil_volume": raw[36],
            "pump_model": raw[37],
            "back_light": raw[38],
            "startup_temp_difference": raw[39],
            "shutdown_temp_difference": raw[40],
            "wifi": raw[41],
            "i_stop": raw[42],
        })
        return parsed
