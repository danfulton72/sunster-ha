"""Look up a heater's product model from its controller part number.

The controller reports only a part number (for example ``11240905``). The
official Sunster app turns that into a product name and model by asking the
manufacturer's (Booyood) server, which needs no account. This module makes
the same request so the device page in Home Assistant shows the real model.

The lookup is optional, runs at most once per Home Assistant start, and only
while the device has no model for its current part number, so existing
installs pick it up automatically. Failures are logged and ignored: the
heater itself is always controlled locally over Bluetooth.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

LOOKUP_URL = "https://www.booyoodapp.com/api/devices/getProductInfo"
# The server serves several brands' apps and expects to be told which one.
_APP_PARAMS = {"appName": "Sunster", "appVersion": "2.2.000"}
_HEADERS = {"Accept-AppName": "Sunster", "Interface-Version": "4", "Accept-Language": "en"}
_TIMEOUT = aiohttp.ClientTimeout(total=15)

# Part numbers that do not identify a product: unset, or the app's own
# placeholder for a controller that reported nothing.
NO_PART_NUMBERS = {"", "00000000", "ffffffff", "11220900"}


def usable_part_number(part_number: Any) -> str | None:
    """Return the part number if it can identify a product."""
    if not isinstance(part_number, str):
        return None
    part_number = part_number.strip().lower()
    if len(part_number) != 8 or part_number in NO_PART_NUMBERS:
        return None
    try:
        int(part_number, 16)
    except ValueError:
        return None
    return part_number


def parse_product(payload: Any) -> dict[str, str] | None:
    """Return the product name and model from a server response, if present."""
    if not isinstance(payload, dict):
        return None
    if payload.get("code") not in (0, 1, "0", "1", None):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    result = {}
    for key, field in (("model", "productModel"), ("name", "productName")):
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result or None


def model_text(product: dict[str, str]) -> str:
    """Return the text for the device's Model field."""
    model, name = product.get("model"), product.get("name")
    if model and name and name.lower() not in model.lower():
        return f"{name} ({model})"
    return model or name or ""


async def async_lookup(session: aiohttp.ClientSession, part_number: str) -> dict[str, str] | None:
    """Ask the manufacturer's server which product a part number belongs to."""
    params = {"modelSn": part_number, **_APP_PARAMS}
    try:
        async with session.get(LOOKUP_URL, params=params, headers=_HEADERS, timeout=_TIMEOUT) as resp:
            if resp.status != 200:
                _LOGGER.debug("Product lookup for %s returned HTTP %s", part_number, resp.status)
                return None
            payload = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
        _LOGGER.debug("Product lookup for %s failed: %s", part_number, err)
        return None
    product = parse_product(payload)
    if product is None:
        _LOGGER.debug("Product lookup for %s found no product: %s", part_number, payload)
    return product
