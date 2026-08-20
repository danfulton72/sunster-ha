from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

SENSORS = [("Raw Run State","raw_run_state"),("Run Step","running_step"),("Error Code","error_code"),("Running Mode","running_mode")]
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SunsterSensor(entry.runtime_data, name, key) for name,key in SENSORS])
class SunsterSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, name, key):
        super().__init__(coordinator); self.key=key; self._attr_name=name; self._attr_unique_id=f"{coordinator.address}_{key}"; self._attr_device_info={"identifiers": {(DOMAIN, coordinator.address)}}
    @property
    def native_value(self):
        return self.coordinator.data.get(self.key)
