from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1] / "custom_components" / "sunster_heater"
spec = importlib.util.spec_from_file_location("sunster_fuel", ROOT / "fuel.py")
fuel = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(fuel)


def running(level: int = 5, **overrides):
    data = {"connected": True, "running_state": 1, "running_mode": 1, "current_level": level}
    data.update(overrides)
    return data


class FuelTests(unittest.TestCase):
    def test_level_rates_span_2kw_rating(self):
        self.assertAlmostEqual(fuel.rate_for_level(1), 0.16)
        self.assertAlmostEqual(fuel.rate_for_level(10), 0.45)
        rates = [fuel.rate_for_level(level) for level in range(1, 11)]
        self.assertEqual(rates, sorted(rates))

    def test_levels_outside_range_are_clamped(self):
        self.assertAlmostEqual(fuel.rate_for_level(0), 0.16)
        self.assertAlmostEqual(fuel.rate_for_level(15), 0.45)

    def test_custom_calibration(self):
        self.assertAlmostEqual(fuel.rate_for_level(1, 0.1, 1.0), 0.1)
        self.assertAlmostEqual(fuel.rate_for_level(10, 0.1, 1.0), 1.0)

    def test_no_fuel_when_off_disconnected_or_ventilating(self):
        self.assertEqual(fuel.fuel_rate(running(running_state=0)), 0.0)
        self.assertEqual(fuel.fuel_rate(running(connected=False)), 0.0)
        self.assertEqual(fuel.fuel_rate(running(running_mode=3)), 0.0)
        self.assertEqual(fuel.fuel_rate(running(level=0)), 0.0)
        self.assertEqual(fuel.fuel_rate({}), 0.0)

    def test_running_rate_follows_current_level(self):
        self.assertAlmostEqual(fuel.fuel_rate(running(level=10)), 0.45)
        self.assertAlmostEqual(fuel.fuel_rate(running(level=1, running_mode=2)), 0.16)

    def test_litres_integration(self):
        # One hour at 0.45 L/h in 15 s steps is 0.45 L.
        total = sum(fuel.litres_used(0.45, 15) for _ in range(240))
        self.assertAlmostEqual(total, 0.45)

    def test_long_gaps_and_clock_jumps_are_not_guessed(self):
        self.assertEqual(fuel.litres_used(0.45, fuel.MAX_GAP_SECONDS + 1), 0.0)
        self.assertEqual(fuel.litres_used(0.45, -5), 0.0)
        self.assertEqual(fuel.litres_used(0.0, 15), 0.0)


class SensorSetTests(unittest.TestCase):
    def test_removed_diagnostics_are_not_created(self):
        tree = ast.parse((ROOT / "sensor.py").read_text())
        keys = {
            node.args[1].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "Description"
            and len(node.args) > 1
        }
        for removed in ("chip_type", "key_mode", "software_version", "protocol_version"):
            self.assertNotIn(removed, keys)
        self.assertIn("current_level", keys)


if __name__ == "__main__":
    unittest.main()
