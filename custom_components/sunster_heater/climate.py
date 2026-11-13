from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

MODE_LEVEL = 1
MODE_TEMPERATURE = 2
MODE_VENTILATION = 3
MODE_PLUS = 4

PRESET_TEMPERATURE = "Temperature"
PRESET_LEVEL = "Level"
PRESET_MAX = "Max"

# Heater modes offered as presets, in display order. Ventilation is the
# fan_only HVAC mode rather than a preset.
PRESET_TO_MODE = {
    PRESET_TEMPERATURE: MODE_TEMPERATURE,
    PRESET_LEVEL: MODE_LEVEL,
    PRESET_MAX: MODE_PLUS,
}
MODE_TO_PRESET = {mode: preset for preset, mode in PRESET_TO_MODE.items()}
HEAT_MODES = tuple(PRESET_TO_MODE.values())

LEVELS = [str(level) for level in range(1, 11)]


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SunsterClimate(entry.runtime_data)])


class SunsterClimate(CoordinatorEntity, ClimateEntity):
    """Thermostat card for the heater.

    HVAC modes: off, heat and (when supported) fan_only for ventilation.
    Presets choose the heating mode: Temperature, Level or Max (Plus / High heat).
    Fan modes "1"-"10" set the heat level in Level mode and the fan speed in
    fan_only. Only the control that matters in the current mode is offered.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_target_temperature_step = 1

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_climate"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.address)}}
        self._last_heat_mode = MODE_TEMPERATURE

    @property
    def _data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def _available_modes(self) -> tuple:
        return tuple(self._data.get("available_modes", (MODE_LEVEL, MODE_TEMPERATURE)))

    @property
    def _mode(self) -> int | None:
        mode = self._data.get("running_mode") or self.coordinator.protocol.last_mode
        return mode if mode in (MODE_LEVEL, MODE_TEMPERATURE, MODE_VENTILATION, MODE_PLUS) else None

    @property
    def _is_on(self) -> bool:
        return self._data.get("running_state") == 1

    def _handle_coordinator_update(self) -> None:
        if self._mode in HEAT_MODES:
            self._last_heat_mode = self._mode
        super()._handle_coordinator_update()

    @property
    def supported_features(self):
        features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.PRESET_MODE
        )
        mode = self._mode
        if mode == MODE_TEMPERATURE:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        elif mode in (MODE_LEVEL, MODE_VENTILATION):
            features |= ClimateEntityFeature.FAN_MODE
        return features

    @property
    def hvac_modes(self):
        modes = [HVACMode.OFF, HVACMode.HEAT]
        if MODE_VENTILATION in self._available_modes:
            modes.append(HVACMode.FAN_ONLY)
        return modes

    @property
    def hvac_mode(self):
        if not self._is_on:
            return HVACMode.OFF
        return HVACMode.FAN_ONLY if self._mode == MODE_VENTILATION else HVACMode.HEAT

    @property
    def preset_modes(self):
        return [preset for preset, mode in PRESET_TO_MODE.items() if mode in self._available_modes]

    @property
    def preset_mode(self):
        return MODE_TO_PRESET.get(self._mode)

    @property
    def fan_modes(self):
        return LEVELS

    @property
    def fan_mode(self):
        if self._mode not in (MODE_LEVEL, MODE_VENTILATION):
            return None
        level = self._data.get("set_level")
        return str(level) if isinstance(level, int) and 1 <= level <= 10 else None

    @property
    def temperature_unit(self):
        return UnitOfTemperature.FAHRENHEIT if self._data.get("temp_unit") == 1 else UnitOfTemperature.CELSIUS

    @property
    def min_temp(self):
        return 46 if self._data.get("temp_unit") == 1 else 8

    @property
    def max_temp(self):
        return 97 if self._data.get("temp_unit") == 1 else 36

    @property
    def current_temperature(self):
        return self._data.get("ambient_temperature")

    @property
    def target_temperature(self):
        if self._mode != MODE_TEMPERATURE:
            return None
        return self._data.get("set_temp", self.coordinator.protocol.last_param)

    async def _ensure_mode(self, mode: int) -> None:
        if self._mode != mode:
            await self.coordinator.set_mode(mode)

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.turn_off()
            return
        if hvac_mode == HVACMode.FAN_ONLY:
            await self._ensure_mode(MODE_VENTILATION)
        elif self._mode not in HEAT_MODES:
            # Leaving ventilation: go back to the last heating mode used.
            mode = self._last_heat_mode if self._last_heat_mode in self._available_modes else MODE_TEMPERATURE
            await self.coordinator.set_mode(mode)
        if not self._is_on:
            await self.coordinator.turn_on()

    async def async_turn_on(self):
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self):
        await self.coordinator.turn_off()

    async def async_set_preset_mode(self, preset_mode):
        mode = PRESET_TO_MODE.get(preset_mode)
        if mode is None or mode not in self._available_modes:
            raise ServiceValidationError(f"Preset {preset_mode} is not supported by this heater")
        await self._ensure_mode(mode)

    async def async_set_fan_mode(self, fan_mode):
        if fan_mode not in LEVELS:
            raise ServiceValidationError(f"Level must be 1-10, got {fan_mode}")
        # In ventilation this sets the fan speed and stays in ventilation;
        # from any heating mode it switches to Level mode at that level.
        await self.coordinator.set_level(int(fan_mode))

    async def async_set_temperature(self, **kwargs):
        # Setting a temperature switches the heater to Temperature mode,
        # as the official app does.
        if (t := kwargs.get("temperature")) is not None:
            await self.coordinator.set_temperature(round(t))
