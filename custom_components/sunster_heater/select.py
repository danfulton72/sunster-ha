from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

MODE_NAMES = {1: "Level", 2: "Temperature", 3: "Ventilation", 4: "High heat"}
LANGUAGE_NAMES = {0: "Off", 1: "English", 2: "Chinese", 3: "Russian", 4: "German", 5: "Turkish", 6: "Korean", 7: "French"}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        SunsterModeSelect(entry.runtime_data),
        SunsterUnitSelect(entry.runtime_data, "Temperature Unit", "temp_unit", "supports_temp_unit", {0: "Celsius", 1: "Fahrenheit"}),
        SunsterUnitSelect(entry.runtime_data, "Altitude Unit", "altitude_unit", "supports_altitude_unit", {0: "Metres", 1: "Feet"}),
        SunsterLanguageSelect(entry.runtime_data),
    ])


class SunsterModeSelect(CoordinatorEntity, SelectEntity):
    _attr_name = "Operating Mode"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_operating_mode"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}

    @property
    def options(self):
        return [MODE_NAMES[m] for m in self.coordinator.data.get("available_modes", (1, 2))]

    @property
    def current_option(self):
        return MODE_NAMES.get(self.coordinator.data.get("running_mode"))

    async def async_select_option(self, option: str) -> None:
        mode = next(mode for mode, name in MODE_NAMES.items() if name == option)
        await self.coordinator.set_mode(mode)


class SunsterUnitSelect(CoordinatorEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, name, key, capability, choices):
        super().__init__(coordinator)
        self._attr_name = name
        self.key = key
        self.capability = capability
        self.choices = choices
        self._attr_options = list(choices.values())
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}

    @property
    def available(self):
        return super().available and bool(self.coordinator.data.get(self.capability))

    @property
    def current_option(self):
        return self.choices.get(self.coordinator.data.get(self.key))

    async def async_select_option(self, option: str) -> None:
        value = next(value for value, name in self.choices.items() if name == option)
        await self.coordinator.set_setting(self.key, value)


class SunsterLanguageSelect(CoordinatorEntity, SelectEntity):
    _attr_name = "Voice Language"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_voice_language"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}

    @property
    def available(self):
        return super().available and bool(self.coordinator.data.get("supports_language")) and bool(self.coordinator.data.get("language_options"))

    @property
    def options(self):
        return [LANGUAGE_NAMES[value] for value in self.coordinator.data.get("language_options", ()) if value in LANGUAGE_NAMES]

    @property
    def current_option(self):
        return LANGUAGE_NAMES.get(self.coordinator.data.get("broadcast_language"))

    async def async_select_option(self, option: str) -> None:
        value = next(value for value, name in LANGUAGE_NAMES.items() if name == option)
        await self.coordinator.set_setting("broadcast_language", value)
