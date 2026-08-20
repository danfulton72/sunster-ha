from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.util.percentage import percentage_to_ranged_value, ranged_value_to_percentage
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SunsterLevel(entry.runtime_data)])

class SunsterLevel(CoordinatorEntity, FanEntity):
    _attr_name = "Level"
    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_speed_count = 10
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_level"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}
    @property
    def is_on(self):
        return self.coordinator.data.get("running_state") == 1
    @property
    def percentage(self):
        lvl = self.coordinator.data.get("set_level")
        return ranged_value_to_percentage((1,10), lvl) if lvl else None
    async def async_set_percentage(self, percentage):
        if percentage == 0:
            await self.coordinator.turn_off(); return
        level = round(percentage_to_ranged_value((1,10), percentage))
        await self.coordinator.set_level(level)
    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        if percentage:
            await self.async_set_percentage(percentage)
        await self.coordinator.turn_on()
    async def async_turn_off(self, **kwargs):
        await self.coordinator.turn_off()
