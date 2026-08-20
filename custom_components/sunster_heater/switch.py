from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SunsterPower(entry.runtime_data)])

class SunsterPower(CoordinatorEntity, SwitchEntity):
    _attr_name = "Power"
    _attr_icon = "mdi:radiator"
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_power"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}, "name": "Sunster Diesel Heater", "manufacturer": "Sunster", "model": "S-A2409PRO"}
    @property
    def is_on(self):
        return self.coordinator.data.get("running_state") == 1
    async def async_turn_on(self, **kwargs):
        await self.coordinator.turn_on()
    async def async_turn_off(self, **kwargs):
        await self.coordinator.turn_off()
