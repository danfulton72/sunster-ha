from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


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
    Description("Protocol Version", "protocol_version", diagnostic=True),
    Description("Mainboard Type", "mainboard_type", diagnostic=True),
    Description("Hardware Version", "hardware_version", diagnostic=True),
    Description("Software Version", "software_version", diagnostic=True),
    Description("Heater Mode", "heater_mode", diagnostic=True),
    Description("Product Part Number", "product_part_number", diagnostic=True),
    Description("Chip Type", "chip_type", diagnostic=True),
    Description("Key Mode", "key_mode", diagnostic=True),
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SunsterSensor(entry.runtime_data, desc) for desc in SENSORS])


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
