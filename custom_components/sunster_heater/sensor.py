from __future__ import annotations

from dataclasses import dataclass
import time

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature, UnitOfVolume
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import CONF_FUEL_MAX_RATE, CONF_FUEL_MIN_RATE, DOMAIN
from .fuel import DEFAULT_MAX_RATE, DEFAULT_MIN_RATE, fuel_rate, litres_used

# Diagnostic sensors that earlier versions created and this version no longer does.
REMOVED_SENSOR_KEYS = ("protocol_version", "software_version", "chip_type", "key_mode")


@dataclass(frozen=True)
class Description:
    name: str
    key: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    diagnostic: bool = False
    capability: str | None = None
    enabled_default: bool = True


SENSORS = (
    Description("Ambient Temperature", "ambient_temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    Description("Heater Temperature", "heater_temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    Description("Supply Voltage", "voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    Description("Altitude", "altitude", None, None, SensorStateClass.MEASUREMENT),
    Description("Current Level", "current_level"),
    Description("Run Step", "running_step", diagnostic=True),
    Description("Raw Run State", "raw_run_state", diagnostic=True),
    Description("Error Code", "error_code", diagnostic=True),
    Description("Fault Code", "fault_code", diagnostic=True),
    Description("Fault Type", "fault_type", diagnostic=True),
    Description("Running Mode", "running_mode", diagnostic=True),
    Description("Mainboard Type", "mainboard_type", diagnostic=True),
    Description("Hardware Version", "hardware_version", diagnostic=True),
    Description("Heater Mode", "heater_mode", diagnostic=True),
    Description("Product Part Number", "product_part_number", diagnostic=True),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    registry = er.async_get(hass)
    for key in REMOVED_SENSOR_KEYS:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{coordinator.address}_{key}")
        if entity_id:
            registry.async_remove(entity_id)

    min_rate = float(entry.options.get(CONF_FUEL_MIN_RATE, DEFAULT_MIN_RATE))
    max_rate = float(entry.options.get(CONF_FUEL_MAX_RATE, DEFAULT_MAX_RATE))
    entities: list[SensorEntity] = [SunsterSensor(coordinator, desc) for desc in SENSORS]
    entities.append(SunsterFuelRateSensor(coordinator, min_rate, max_rate))
    entities.append(SunsterFuelUsedSensor(coordinator, min_rate, max_rate))
    async_add_entities(entities)


class SunsterSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, desc: Description):
        super().__init__(coordinator)
        self.desc = desc
        self._attr_name = desc.name
        self._attr_unique_id = f"{coordinator.address}_{desc.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}
        self._attr_native_unit_of_measurement = desc.unit
        self._attr_device_class = desc.device_class
        self._attr_state_class = desc.state_class
        self._attr_entity_registry_enabled_default = desc.enabled_default
        if desc.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self):
        return super().available and (not self.desc.capability or bool(self.coordinator.data.get(self.desc.capability))) and self.coordinator.data.get(self.desc.key) is not None

    @property
    def native_unit_of_measurement(self):
        if self.desc.key == "altitude":
            return "ft" if self.coordinator.data.get("altitude_unit") == 1 else "m"
        if self.desc.key in ("ambient_temperature", "heater_temperature"):
            return UnitOfTemperature.FAHRENHEIT if self.coordinator.data.get("temp_unit") == 1 else UnitOfTemperature.CELSIUS
        return self.desc.unit

    @property
    def native_value(self):
        return self.coordinator.data.get(self.desc.key)


class _SunsterFuelBase(CoordinatorEntity):
    def __init__(self, coordinator, key: str, name: str, min_rate: float, max_rate: float):
        super().__init__(coordinator)
        self._min_rate = min_rate
        self._max_rate = max_rate
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}
        self._attr_icon = "mdi:fuel"

    def _current_rate(self) -> float:
        if not self.coordinator.last_update_success:
            return 0.0
        return fuel_rate(self.coordinator.data or {}, self._min_rate, self._max_rate)


class SunsterFuelRateSensor(_SunsterFuelBase, SensorEntity):
    """Estimated diesel consumption right now, from the current heater level."""

    _attr_native_unit_of_measurement = "L/h"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator, min_rate: float, max_rate: float):
        super().__init__(coordinator, "fuel_rate", "Fuel Consumption Rate", min_rate, max_rate)

    @property
    def native_value(self):
        return self._current_rate()


class SunsterFuelUsedSensor(_SunsterFuelBase, RestoreSensor):
    """Estimated diesel burnt in total, integrated from the consumption rate."""

    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, min_rate: float, max_rate: float):
        super().__init__(coordinator, "fuel_used", "Fuel Used", min_rate, max_rate)
        self._total = 0.0
        self._last_rate = 0.0
        self._last_time: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._total = max(0.0, float(last.native_value))
            except (TypeError, ValueError):
                self._total = 0.0
        self._last_rate = self._current_rate()
        self._last_time = time.monotonic()

    @callback
    def _handle_coordinator_update(self) -> None:
        now = time.monotonic()
        if self._last_time is not None:
            # Left Riemann sum: the rate seen at the previous update applies until now.
            self._total += litres_used(self._last_rate, now - self._last_time)
        self._last_rate = self._current_rate()
        self._last_time = now
        super()._handle_coordinator_update()

    @property
    def available(self):
        # The running total stays meaningful while the heater is out of range.
        return True

    @property
    def native_value(self):
        return round(self._total, 4)
