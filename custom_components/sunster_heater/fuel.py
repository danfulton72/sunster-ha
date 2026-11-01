"""Estimated diesel consumption for Sunster heaters.

The controller does not report fuel flow. Each heater level is a fixed fuel-pump
pulse rate, so consumption is estimated from the current level, interpolated
linearly between the heater's minimum and maximum rated consumption.
"""
from __future__ import annotations

from typing import Any

# Sunster SH B2 / A2200BS 2 kW split heater: rated 0.16-0.45 L/h.
DEFAULT_MIN_RATE = 0.16
DEFAULT_MAX_RATE = 0.45
MIN_LEVEL = 1
MAX_LEVEL = 10
RUN_MODE_VENTILATION = 3

# Longest gap between two status updates that is integrated. A longer gap means
# Home Assistant lost the heater (restart, Bluetooth dropout), and the burn
# during that time is unknown, so it is not guessed.
MAX_GAP_SECONDS = 300.0


def rate_for_level(level: int, min_rate: float = DEFAULT_MIN_RATE, max_rate: float = DEFAULT_MAX_RATE) -> float:
    """Return litres per hour for a heater level 1-10."""
    level = max(MIN_LEVEL, min(MAX_LEVEL, int(level)))
    step = (max_rate - min_rate) / (MAX_LEVEL - MIN_LEVEL)
    return round(min_rate + (level - MIN_LEVEL) * step, 4)


def is_burning(data: dict[str, Any]) -> bool:
    """Return True when the status frame indicates fuel is being burnt."""
    if not data.get("connected") or not data.get("running_state"):
        return False
    if data.get("running_mode") == RUN_MODE_VENTILATION:
        return False
    level = data.get("current_level")
    return isinstance(level, int) and MIN_LEVEL <= level <= MAX_LEVEL


def fuel_rate(data: dict[str, Any], min_rate: float = DEFAULT_MIN_RATE, max_rate: float = DEFAULT_MAX_RATE) -> float:
    """Return the estimated consumption in L/h for a parsed status frame."""
    if not is_burning(data):
        return 0.0
    return rate_for_level(data["current_level"], min_rate, max_rate)


def litres_used(rate_lph: float, elapsed_seconds: float) -> float:
    """Return litres burnt at ``rate_lph`` over ``elapsed_seconds``.

    Gaps longer than MAX_GAP_SECONDS (or negative clock jumps) count as zero.
    """
    if rate_lph <= 0 or elapsed_seconds <= 0 or elapsed_seconds > MAX_GAP_SECONDS:
        return 0.0
    return rate_lph * elapsed_seconds / 3600.0
