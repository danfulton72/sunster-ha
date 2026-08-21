from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


DESCRIPTIONS = (
    ("Temperature Offset", "temp_comp", None),
    ("Back Light Level", "back_light", "supports_back_light"),
    ("Start Temp Offset", "startup_temp_difference", "supports_startup_temp_difference"),
    ("Stop Temp Offset", "shutdown_temp_difference", "supports_shutdown_temp_difference"),
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SunsterSettingNumber(entry.runtime_data, *desc) for desc in DESCRIPTIONS])


class SunsterSettingNumber(CoordinatorEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_step = 1

    def __init__(self, coordinator, name, key, capability):
        super().__init__(coordinator)
        self._attr_name = name
        self.key = key
        self.capability = capability
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}

    @property
    def available(self):
        return super().available and (self.capability is None or bool(self.coordinator.data.get(self.capability)))

    @property
    def native_min_value(self):
        fahrenheit = self.coordinator.data.get("temp_unit") == 1
        if self.key == "temp_comp":
            return -27 if fahrenheit else -15
        if self.key == "startup_temp_difference":
            return 2 if fahrenheit else 1
        return 0

    @property
    def native_max_value(self):
        fahrenheit = self.coordinator.data.get("temp_unit") == 1
        if self.key == "temp_comp":
            return 27 if fahrenheit else 15
        if self.key in ("startup_temp_difference", "shutdown_temp_difference"):
            return 18 if fahrenheit else 10
        if self.key == "back_light":
            return 10
        return 100

    @property
    def native_unit_of_measurement(self):
        if self.key in ("temp_comp", "startup_temp_difference", "shutdown_temp_difference"):
            return UnitOfTemperature.FAHRENHEIT if self.coordinator.data.get("temp_unit") == 1 else UnitOfTemperature.CELSIUS
        return None

    @property
    def native_value(self):
        return self.coordinator.data.get(self.key)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.set_setting(self.key, round(value))
