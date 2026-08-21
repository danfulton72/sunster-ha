from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "sunster_heater" / "protocol.py"
spec = importlib.util.spec_from_file_location("sunster_protocol", MODULE_PATH)
protocol_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(protocol_module)
SunsterProtocol = protocol_module.SunsterProtocol
convert_temperature_setting = protocol_module.convert_temperature_setting


class ProtocolTests(unittest.TestCase):
    def make_status(self, *, protocol_version: int = 1) -> bytearray:
        raw = bytearray(47)
        raw[0:2] = b"\xfe\xaa"
        raw[2] = protocol_version
        raw[6] = 0x80
        raw[7] = 0
        raw[8] = 11
        raw[10] = 2
        raw[11] = 2
        raw[12] = 21
        raw[13] = 4
        raw[14] = 3
        raw[15] = 0
        raw[16] = 0
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
        self.assertEqual(data["mainboard_type"], 11)
        self.assertEqual(data["available_modes"], (1, 2, 3))
        self.assertEqual(data["ambient_temperature"], 19)
        self.assertEqual(data["altitude"], 123)
        self.assertEqual(data["voltage"], 12.8)
        self.assertEqual(data["heater_temperature"], 87.6)
        self.assertEqual(data["temp_comp"], -2)
        self.assertFalse(data["supports_fuel_tank"])
        self.assertFalse(data["supports_pump_model"])
        self.assertTrue(data["supports_back_light"])
        self.assertEqual(data["remaining_runtime"], 45)

    def test_newer_protocol_altitude_scale_and_co_sentinel(self):
        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        raw = self.make_status(protocol_version=2)
        raw[27:29] = (65530).to_bytes(2, "little")
        data = protocol.parse_notification(raw)
        assert data is not None
        self.assertEqual(data["altitude"], 12.3)
        self.assertIsNone(data["co"])

    def test_fahrenheit_target_temperature_is_not_celsius_clamped(self):
        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        raw = self.make_status()
        raw[17] = 1
        raw[12] = 75
        data = protocol.parse_notification(raw)
        assert data is not None
        self.assertEqual(data["temp_unit"], 1)
        self.assertEqual(data["set_temp"], 75)

    def test_extended_fault_code_uses_apk_fault_type(self):
        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        raw = self.make_status()
        raw[15] = 7
        raw[16] = 130
        data = protocol.parse_notification(raw)
        assert data is not None
        self.assertEqual(data["error_code"], 7)
        self.assertEqual(data["fault_type"], "JW")

    def test_settings_write_preserves_unsupported_tank_fields(self):
        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        protocol.parse_notification(self.make_status())
        packet = protocol.update_settings(back_light=4)
        payload = packet[8:-1]
        self.assertEqual(packet[6:8], bytes([3, 1]))
        self.assertEqual(payload[6], 0xFF)
        self.assertEqual(payload[7], 0xFF)
        self.assertEqual(payload[8], 4)
        self.assertEqual(payload[9], 2)
        self.assertEqual(payload[10], 3)
        self.assertEqual(payload[11], 1)
        self.assertEqual(payload[12], 0)

    def test_fixed_unit_capability_bytes_use_apk_write_encoding(self):
        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        raw = self.make_status()
        raw[17] = 0xF1
        raw[20] = 0xF3
        data = protocol.parse_notification(raw)
        assert data is not None
        self.assertEqual(data["temp_unit"], 1)
        self.assertFalse(data["supports_temp_unit"])
        self.assertEqual(data["altitude_unit"], 1)
        self.assertFalse(data["supports_altitude_unit"])
        packet = protocol.update_settings(back_light=4)
        payload = packet[8:-1]
        self.assertEqual(payload[0], 0x81)
        self.assertEqual(payload[1], 0x81)

    def test_time_sync_uses_apk_date_overlay_without_losing_settings_tail(self):
        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        protocol.parse_notification(self.make_status())
        packet = protocol.time_sync(datetime(2026, 8, 21, 8, 47))
        payload = packet[8:-1]
        minutes = payload[2] | (payload[3] << 8)
        self.assertEqual(minutes, 0x8000 | (8 * 60 + 47))
        self.assertEqual(payload[4], 2026 & 0xFF)
        self.assertEqual(payload[5], 8)
        self.assertEqual(payload[6], 21)
        self.assertEqual(payload[7], 5)
        self.assertEqual(payload[8], 5)
        self.assertEqual(payload[11], 1)

    def test_mode_defaults_match_local_app(self):
        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        packet = protocol.set_mode(2)
        self.assertEqual(packet[8:10], bytes([2, 24]))
        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        protocol.settings["temp_unit_raw"] = 1
        packet = protocol.set_mode(2)
        self.assertEqual(packet[8:10], bytes([2, 75]))
        protocol.last_mode = 2
        protocol.last_param = 21
        packet = protocol.set_mode(4)
        self.assertEqual(packet[8:10], bytes([4, 21]))

    def test_short_device_info_frame_for_11240905(self):
        protocol = SunsterProtocol("AA:BB:CC:DD:EE:FF")
        raw = bytearray(25)
        raw[0:2] = b"\xfe\xaa"
        raw[6:8] = bytes([0x80, 0x03])
        raw[8:12] = bytes([0x05, 0x09, 0x24, 0x11])
        raw[12:14] = (0).to_bytes(2, "little")
        raw[14:16] = (4).to_bytes(2, "little")
        raw[16:18] = (13).to_bytes(2, "little")
        data = protocol.parse_notification(raw)
        assert data is not None
        self.assertEqual(data["product_part_number"], "11240905")
        self.assertEqual(data["device_software_version"], 4)
        self.assertFalse(data["supports_fuel_tank"])
        self.assertFalse(data["supports_pump_model"])
        self.assertFalse(data["supports_co"])
        self.assertFalse(data["supports_remaining_runtime"])
        self.assertNotIn("chip_type", data)
        self.assertNotIn("key_mode", data)

    def test_temperature_setting_conversion_matches_app(self):
        self.assertEqual(convert_temperature_setting(5, 0, 1), 9)
        self.assertEqual(convert_temperature_setting(-5, 0, 1), -9)
        self.assertEqual(convert_temperature_setting(9, 1, 0), 5)
        self.assertEqual(convert_temperature_setting(-9, 1, 0), -5)


if __name__ == "__main__":
    unittest.main()
