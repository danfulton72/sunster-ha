from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        SunsterPower(entry.runtime_data),
        SunsterSettingSwitch(entry.runtime_data, "Auto Start/Stop", "auto_start_stop", "supports_auto_start_stop", "i_stop", True),
        SunsterSettingSwitch(entry.runtime_data, "Controller Wi-Fi", "wifi_enabled", "supports_wifi", "wifi", False),
    ])


class SunsterPower(CoordinatorEntity, SwitchEntity):
    _attr_name = "Power"
    _attr_entity_registry_enabled_default = False
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


class SunsterSettingSwitch(CoordinatorEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, name, key, capability, setting_key, enabled_default):
        super().__init__(coordinator)
        self._attr_name = name
        self.key = key
        self.capability = capability
        self.setting_key = setting_key
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}

    @property
    def available(self):
        return super().available and bool(self.coordinator.data.get(self.capability))

    @property
    def is_on(self):
        return bool(self.coordinator.data.get(self.key))

    async def async_turn_on(self, **kwargs):
        await self.coordinator.set_setting(self.setting_key, 1)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.set_setting(self.setting_key, 0)
