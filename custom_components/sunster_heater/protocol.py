from __future__ import annotations
from datetime import datetime
from typing import Any

SUNSTER_KEY = b"passwordA2409PW"


def _xor_repeat(data: bytes | bytearray, key: bytes) -> bytearray:
    return bytearray(b ^ key[i % len(key)] for i, b in enumerate(data))


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
        if mode == 1:
            param = self.last_param if self.last_mode == 1 else 5
        else:
            param = self.last_param if self.last_mode == 2 else 21
        self.last_mode = mode
        self.last_param = param
        payload = bytes([mode, param, 0xFF, 0xFF])
        return self._wrap(self._feaa(0x01, 0x01 if self.is_on else 0x00, payload))

    def time_sync(self, dt: datetime) -> bytearray:
        mins = 0x8000 | (dt.hour * 60 + dt.minute)
        dow = (dt.weekday() + 1) % 7
        def b(name: str, default: int) -> int:
            v = self.settings.get(name, default)
            if isinstance(v, bool):
                v = 1 if v else 0
            return int(default if v is None else v) & 0xFF
        payload = bytes([
            b("altitude_unit", 0), b("temp_unit", 0),
            mins & 0xFF, (mins >> 8) & 0xFF,
            dt.year & 0xFF, dt.month, dt.day, dow,
            b("backlight", 5), b("startup_temp_diff", 2), b("shutdown_temp_diff", 2),
            b("wifi_enabled", 1), b("auto_start_stop", 0),
        ])
        return self._wrap(self._feaa(0x03, 0x01, payload))

    def parse_notification(self, data: bytearray) -> dict[str, Any] | None:
        if len(data) >= 2 and data[0:2] == b"\xAA\x77":
            self.v21 = True
            return {"aa77": True}
        if len(data) < 46:
            return None
        raw = self.decrypt(data) if self.v21 else bytearray(data)
        if len(raw) < 46:
            return None
        run_state = raw[10]
        run_mode = raw[11]
        run_param = raw[12]
        now_gear = raw[13]
        run_step = raw[14]
        on = run_state in (2, 5, 6)
        parsed: dict[str, Any] = {
            "connected": True,
            "raw_run_state": run_state,
            "running_state": 1 if on else 0,
            "running_mode": run_mode if run_mode in (1, 2, 3) else 0,
            "running_step": run_step,
            "error_code": raw[15] & 0x3F,
        }
        if run_mode == 1:
            parsed["set_level"] = max(1, min(10, run_param))
        elif run_mode == 2:
            parsed["set_temp"] = max(8, min(36, run_param))
            parsed["set_level"] = max(1, min(10, now_gear))
        self.is_on = on
        if on and run_mode in (1, 2):
            self.last_mode = run_mode
            self.last_param = run_param
        if len(raw) > 36:
            parsed["backlight"] = raw[36]
        if len(raw) > 31:
            parsed["auto_start_stop"] = bool(raw[31])
        parsed.setdefault("wifi_enabled", self.settings.get("wifi_enabled", True))
        self.settings.update({k: v for k, v in parsed.items() if k in {
            "backlight", "auto_start_stop", "wifi_enabled", "temp_unit", "altitude_unit",
            "startup_temp_diff", "shutdown_temp_diff"
        }})
        return parsed
