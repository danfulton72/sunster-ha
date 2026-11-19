from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import SunsterCoordinator

PLATFORMS = [Platform.SWITCH, Platform.CLIMATE, Platform.SENSOR, Platform.NUMBER, Platform.SELECT]


async def async_setup_entry(hass, entry):
    address = entry.data[CONF_ADDRESS]
    device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    if device is None:
        raise ConfigEntryNotReady(f"Sunster heater {address} not currently discoverable")
    # The device carries the heater's name; every entity name is built from it,
    # so renaming the device in Home Assistant renames all of them. Entries
    # created before naming was added keep the original name.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        manufacturer="Sunster",
        model="S-A2409PRO",
    )
    coord = SunsterCoordinator(hass, device, entry)
    entry.runtime_data = coord
    await coord.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        await entry.runtime_data.shutdown()
    return ok
