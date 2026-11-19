from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_MODEL_LOOKUP, DEFAULT_NAME, DOMAIN
from .coordinator import SunsterCoordinator
from .product import async_lookup, model_text, usable_part_number

# Model that versions before 0.6.0 gave every heater, whatever it was.
LEGACY_MODEL = "S-A2409PRO"

PLATFORMS = [Platform.SWITCH, Platform.CLIMATE, Platform.SENSOR, Platform.NUMBER, Platform.SELECT]


async def async_setup_entry(hass, entry):
    address = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(f"Sunster heater {address} not currently discoverable")
    # The device carries the heater's name; every entity name is built from it,
    # so renaming the device in Home Assistant renames all of them. Entries
    # created before naming was added keep the original name.
    device_entry = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        manufacturer="Sunster",
    )
    coord = SunsterCoordinator(hass, ble_device, entry)
    entry.runtime_data = coord
    await coord.async_config_entry_first_refresh()
    _async_setup_model_lookup(hass, entry, coord, device_entry.id)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


def _async_setup_model_lookup(hass, entry, coord, device_id) -> None:
    """Fill in the device's model from its part number when it is missing.

    Runs for new and existing installs alike: the part number is recorded as
    the device's model ID, and while the device has no real model for that
    part number the manufacturer's server is asked once per start.
    """
    registry = dr.async_get(hass)
    lookup_enabled = entry.options.get(CONF_MODEL_LOOKUP, True)
    handled: set[str] = set()

    async def _async_lookup(part_number: str, had_legacy_model: bool) -> None:
        product = await async_lookup(async_get_clientsession(hass), part_number)
        if product and (model := model_text(product)):
            registry.async_update_device(device_id, model=model)
        elif had_legacy_model:
            # The old hard-coded model is wrong for most heaters; drop it.
            registry.async_update_device(device_id, model=None)

    @callback
    def _async_check() -> None:
        part_number = usable_part_number((coord.data or {}).get("product_part_number"))
        if part_number is None or part_number in handled:
            return
        handled.add(part_number)
        device = registry.async_get(device_id)
        if device is None:
            return
        known = device.model_id == part_number and device.model and device.model != LEGACY_MODEL
        legacy = device.model == LEGACY_MODEL
        if device.model_id != part_number:
            registry.async_update_device(
                device_id, model_id=part_number, model=None if not legacy else device.model
            )
        if known:
            return
        if lookup_enabled:
            entry.async_create_background_task(
                hass, _async_lookup(part_number, legacy), "sunster_heater_product_lookup"
            )
        elif legacy:
            registry.async_update_device(device_id, model=None)

    entry.async_on_unload(coord.async_add_listener(_async_check))
    _async_check()


async def _reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        await entry.runtime_data.shutdown()
    return ok
