"""Config flow for the Sunster diesel heater integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS

from .const import CONF_PIN, DEFAULT_PIN, DOMAIN, SERVICE_UUID

_LOGGER = logging.getLogger(__name__)


def _normalise_address(address: str) -> str:
    """Normalise a Bluetooth address for storage and unique IDs."""
    return address.upper()


def _is_sunster(discovery_info: BluetoothServiceInfoBleak) -> bool:
    """Return True when an advertisement exposes the Sunster BLE service."""
    return SERVICE_UUID.lower() in {
        service_uuid.lower() for service_uuid in discovery_info.service_uuids
    }


def _title(discovery_info: BluetoothServiceInfoBleak) -> str:
    """Build a friendly title for a discovered heater."""
    address = _normalise_address(discovery_info.address)
    suffix = address[-5:].replace(":", "").replace("-", "")
    name = discovery_info.name or "Sunster Heater"
    return f"{name} {suffix}"


class SunsterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle configuration for a Sunster heater."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ):
        """Handle a heater discovered automatically by Home Assistant."""
        if not _is_sunster(discovery_info):
            return self.async_abort(reason="not_supported")

        address = _normalise_address(discovery_info.address)
        _LOGGER.debug(
            "Discovered Sunster heater %s (%s)",
            discovery_info.name or "unknown name",
            address,
        )

        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": _title(discovery_info)}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ):
        """Confirm an automatically discovered heater and collect its PIN."""
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        address = _normalise_address(discovery_info.address)
        title = _title(discovery_info)

        if user_input is not None:
            return self.async_create_entry(
                title=title,
                data={
                    CONF_ADDRESS: address,
                    CONF_PIN: user_input.get(CONF_PIN, DEFAULT_PIN),
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PIN, default=DEFAULT_PIN): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=9999)
                    )
                }
            ),
            description_placeholders={"name": title},
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Scan for nearby heaters and let the user select one."""
        if user_input is not None:
            address = _normalise_address(user_input[CONF_ADDRESS])
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            discovery_info = self._discovered_devices[address]
            return self.async_create_entry(
                title=_title(discovery_info),
                data={
                    CONF_ADDRESS: address,
                    CONF_PIN: user_input.get(CONF_PIN, DEFAULT_PIN),
                },
            )

        await bluetooth.async_request_active_scan(self.hass)
        current_addresses = {
            _normalise_address(address)
            for address in self._async_current_ids(include_ignore=False)
        }

        for discovery_info in bluetooth.async_discovered_service_info(self.hass):
            if not _is_sunster(discovery_info):
                continue
            address = _normalise_address(discovery_info.address)
            if address in current_addresses:
                continue
            self._discovered_devices[address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        devices = {
            address: f"{_title(info)} ({address})"
            for address, info in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(devices),
                    vol.Optional(CONF_PIN, default=DEFAULT_PIN): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=9999)
                    ),
                }
            ),
        )
