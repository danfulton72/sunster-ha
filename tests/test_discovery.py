from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
CONFIG_FLOW = ROOT / "custom_components" / "sunster_heater" / "config_flow.py"
MANIFEST = ROOT / "custom_components" / "sunster_heater" / "manifest.json"
STRINGS = ROOT / "custom_components" / "sunster_heater" / "strings.json"
SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"


class BluetoothDiscoveryTests(unittest.TestCase):
    def test_manifest_registers_connectable_ffe0_discovery(self):
        manifest = json.loads(MANIFEST.read_text())
        self.assertTrue(
            any(
                matcher.get("connectable") is True
                and matcher.get("service_uuid", "").lower() == SERVICE_UUID
                for matcher in manifest.get("bluetooth", [])
            )
        )

    def test_config_flow_has_bluetooth_discovery_and_active_scan(self):
        source = CONFIG_FLOW.read_text()
        tree = ast.parse(source)
        async_methods = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef)
        }
        self.assertIn("async_step_bluetooth", async_methods)
        self.assertIn("async_step_bluetooth_confirm", async_methods)
        self.assertIn("async_step_user", async_methods)
        self.assertIn("async_request_active_scan", source)
        self.assertIn("async_discovered_service_info", source)
        self.assertIn("vol.In(devices)", source)

    def test_discovery_strings_cover_confirmation_and_no_devices(self):
        strings = json.loads(STRINGS.read_text())
        config = strings["config"]
        self.assertIn("bluetooth_confirm", config["step"])
        self.assertIn("no_devices_found", config["abort"])
        self.assertEqual(
            config["step"]["user"]["data"]["address"], "Discovered heater"
        )


if __name__ == "__main__":
    unittest.main()
