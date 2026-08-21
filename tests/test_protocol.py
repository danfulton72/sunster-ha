from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "sunster_heater" / "protocol.py"
spec = importlib.util.spec_from_file_location("sunster_protocol", MODULE_PATH)
protocol_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(protocol_module)
SunsterProtocol = protocol_module.SunsterProtocol


class ProtocolTests(unittest.TestCase):
    def make_status(self) -> bytearray:
        raw = bytearray(47)
        raw[0:2] = b"\xfe\xaa"
        raw[2] = 1
        raw[6] = 0x80
        raw[7] = 0
        raw[8] = 11
        raw[10] = 2
        raw[11] = 2
        raw[12] = 21
        raw[13] = 4
        raw[14] = 3
        raw[17] = 0
        raw[18:20] = (19).to_bytes(2, "little", signed=True)
        raw[20] = 0
        raw[21:23] = (123).to_bytes(2, "little")
        raw[23:25] = (128).to_bytes(2, "little")
        raw[25:27] = (876).to_bytes(2, "little", signed=True)
        raw[27:29] = (12).to_bytes(2, "little")
        raw[30:32] = (0x0102).to_bytes(2, "little")
        raw[32:34] = (0x0203).to_bytes(2, "little")
        raw[34] = 0xFE
        raw[35] = 1
        raw[36] = 0xFF
        raw[37] = 0xFF
        raw[38] = 5
        raw[39] = 2
        raw[40] = 3
        raw[41] = 1
        raw[42] = 0
        raw[43] = 2
        raw[44:46] = (45).to_bytes(2, "little")
        raw[-1] = sum(raw[:-1]) & 0xFF
        return raw

    def test_v21_status_layout_and_no_tank_capability(self):
        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        data = protocol.parse_notification(self.make_status())
        assert data is not None
        self.assertEqual(data["_response_cmd"], (0, 0))
        self.assertEqual(data["available_modes"], (1, 2, 3))
        self.assertEqual(data["ambient_temperature"], 19)
        self.assertEqual(data["voltage"], 12.8)
        self.assertEqual(data["heater_temperature"], 87.6)
        self.assertEqual(data["temp_comp"], -2)
        self.assertFalse(data["supports_fuel_tank"])
        self.assertFalse(data["supports_pump_model"])
        self.assertTrue(data["supports_back_light"])
        self.assertEqual(data["remaining_runtime"], 45)

    def test_settings_write_preserves_unsupported_tank_fields(self):
        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        protocol.parse_notification(self.make_status())
        packet = protocol.update_settings(back_light=4)
        payload = packet[8:-1]
        self.assertEqual(payload[6], 0xFF)
        self.assertEqual(payload[7], 0xFF)
        self.assertEqual(payload[8], 4)
        self.assertEqual(payload[9], 2)
        self.assertEqual(payload[10], 3)
        self.assertEqual(payload[11], 1)
        self.assertEqual(payload[12], 0)

    def test_time_sync_preserves_settings_tail(self):
        from datetime import datetime

        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        protocol.parse_notification(self.make_status())
        packet = protocol.time_sync(datetime(2026, 8, 21, 8, 47))
        payload = packet[8:-1]
        self.assertEqual(payload[2] | (payload[3] << 8), 0x8000 | (8 * 60 + 47))
        self.assertEqual(payload[4], 2026 & 0xFF)
        self.assertEqual(payload[5], 8)
        self.assertEqual(payload[6], 21)
        self.assertEqual(payload[8], 5)
        self.assertEqual(payload[11], 1)


if __name__ == "__main__":
    unittest.main()
