from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

try:
    import aiohttp  # noqa: F401
except ImportError:  # CI runs these tests without Home Assistant's dependencies.
    stub = types.ModuleType("aiohttp")
    stub.ClientTimeout = lambda **kwargs: None
    stub.ClientError = Exception
    stub.ClientSession = object
    sys.modules["aiohttp"] = stub

ROOT = Path(__file__).parents[1] / "custom_components" / "sunster_heater"
spec = importlib.util.spec_from_file_location("sunster_product", ROOT / "product.py")
product = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(product)


class PartNumberTests(unittest.TestCase):
    def test_real_part_numbers_are_usable(self):
        self.assertEqual(product.usable_part_number("11240905"), "11240905")
        self.assertEqual(product.usable_part_number(" 1124ABCD "), "1124abcd")

    def test_placeholders_and_junk_are_not_looked_up(self):
        for value in (None, "", "00000000", "ffffffff", "11220900", "1124", "zzzzzzzz", 11240905):
            self.assertIsNone(product.usable_part_number(value), value)


class ResponseTests(unittest.TestCase):
    def test_product_found(self):
        payload = {"code": 0, "data": {"productName": "Diesel Heater", "productModel": "YAH-A2409PW", "productModelSn": "11240905"}}
        self.assertEqual(product.parse_product(payload), {"name": "Diesel Heater", "model": "YAH-A2409PW"})

    def test_success_code_variants(self):
        for code in (0, 1, "0", "1", None):
            payload = {"data": {"productModel": "YAH-A2209BWI"}}
            if code is not None:
                payload["code"] = code
            self.assertEqual(product.parse_product(payload), {"model": "YAH-A2209BWI"})

    def test_no_product(self):
        for payload in (None, [], {}, {"code": 0, "data": None}, {"code": 0, "data": {}},
                        {"code": 0, "data": {"productModel": "  "}}, {"code": 500, "data": {"productModel": "X"}}):
            self.assertIsNone(product.parse_product(payload), payload)

    def test_model_text(self):
        self.assertEqual(product.model_text({"name": "Diesel Heater", "model": "YAH-A2409PW"}), "Diesel Heater (YAH-A2409PW)")
        self.assertEqual(product.model_text({"model": "YAH-A2409PW"}), "YAH-A2409PW")
        self.assertEqual(product.model_text({"name": "Diesel Heater"}), "Diesel Heater")
        # Do not repeat a name that is already part of the model.
        self.assertEqual(product.model_text({"name": "TP B2", "model": "TP B2 8KW"}), "TP B2 8KW")


if __name__ == "__main__":
    unittest.main()
