from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SunsterClimate(entry.runtime_data)])

class SunsterClimate(CoordinatorEntity, ClimateEntity):
    _attr_name = "Heater"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 8
    _attr_max_temp = 36
    _attr_target_temperature_step = 1
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_climate"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}
    @property
    def hvac_mode(self):
        return HVACMode.HEAT if self.coordinator.data.get("running_state") == 1 else HVACMode.OFF
    @property
    def target_temperature(self):
        return self.coordinator.data.get("set_temp", self.coordinator.protocol.last_param if self.coordinator.protocol.last_mode == 2 else None)
    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.turn_on()
        else:
            await self.coordinator.turn_off()
    async def async_set_temperature(self, **kwargs):
        if (t := kwargs.get("temperature")) is not None:
            await self.coordinator.set_temperature(round(t))
