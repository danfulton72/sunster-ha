from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS
from .const import CONF_PIN, DEFAULT_PIN, DOMAIN

class SunsterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"Sunster {address[-5:]}", data={CONF_ADDRESS: address, CONF_PIN: user_input[CONF_PIN]})
        schema = vol.Schema({vol.Required(CONF_ADDRESS): str, vol.Required(CONF_PIN, default=DEFAULT_PIN): vol.All(vol.Coerce(int), vol.Range(min=0,max=9999))})
        return self.async_show_form(step_id="user", data_schema=schema)
