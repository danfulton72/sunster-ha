from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


DESCRIPTIONS = (
    ("Temperature Offset", "temp_comp", None, -10, 10, 1, "°C"),
    ("Back Light Level", "back_light", "supports_back_light", 0, 5, 1, None),
    ("Start Temp Offset", "startup_temp_difference", "supports_startup_temp_difference", 0, 10, 1, "°C"),
    ("Stop Temp Offset", "shutdown_temp_difference", "supports_shutdown_temp_difference", 0, 10, 1, "°C"),
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SunsterSettingNumber(entry.runtime_data, *desc) for desc in DESCRIPTIONS])


class SunsterSettingNumber(CoordinatorEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, name, key, capability, minimum, maximum, step, unit):
        super().__init__(coordinator)
        self._attr_name = name
        self.key = key
        self.capability = capability
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit

    @property
    def available(self):
        return super().available and (self.capability is None or bool(self.coordinator.data.get(self.capability)))

    @property
    def native_value(self):
        return self.coordinator.data.get(self.key)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.set_setting(self.key, round(value))
