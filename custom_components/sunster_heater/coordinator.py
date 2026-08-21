from __future__ import annotations
import asyncio
import logging
from datetime import timedelta
from typing import Any

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CHAR_UUID, DEFAULT_PIN, DOMAIN, UPDATE_INTERVAL
from .protocol import SunsterProtocol

_LOGGER = logging.getLogger(__name__)


class SunsterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, ble_device: bluetooth.BleakDevice, entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=UPDATE_INTERVAL))
        self.ble_device = ble_device
        self.address = ble_device.address
        self.pin = int(entry.data.get("pin", DEFAULT_PIN))
        self.protocol = SunsterProtocol(self.address)
        self.client: BleakClient | None = None
        self._notification = asyncio.Event()
        self._expected_response: tuple[int, int] | None = None
        self._handshake_sent = False
        self._lock = asyncio.Lock()
        self.data = {"connected": False, "running_state": 0}

    @callback
    def _notify(self, _sender, data: bytearray) -> None:
        parsed = self.protocol.parse_notification(bytearray(data))
        if parsed:
            if parsed.pop("aa77", False):
                if not self._handshake_sent:
                    self._handshake_sent = True
                    self.hass.async_create_task(self._send_handshake())
                self._notification.set()
            else:
                response_cmd = parsed.pop("_response_cmd", None)
                self.data.update(parsed)
                if not self.protocol.v21 or self._expected_response is None or response_cmd == self._expected_response:
                    self._notification.set()
            return
        if not self.protocol.v21:
            self._notification.set()

    async def _send_handshake(self) -> None:
        try:
            await asyncio.sleep(0.2)
            if self.client and self.client.is_connected:
                await self.client.write_gatt_char(CHAR_UUID, self.protocol.handshake(self.pin), response=False)
        except Exception:
            self._handshake_sent = False
            _LOGGER.exception("Sunster V2.1 handshake failed")

    async def _connect(self) -> None:
        if self.client and self.client.is_connected:
            return
        self._handshake_sent = False
        self.protocol.v21 = False
        self.client = await establish_connection(BleakClient, self.ble_device, self.address, max_attempts=3)
        await self.client.start_notify(CHAR_UUID, self._notify)
        self._notification.clear()
        await self.client.write_gatt_char(CHAR_UUID, self.protocol.wakeup(self.pin), response=False)
        try:
            await asyncio.wait_for(self._notification.wait(), 2.0)
        except TimeoutError:
            pass
        if self.protocol.v21:
            for _ in range(20):
                if self._handshake_sent:
                    break
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.35)
        ok = await self._send(self.protocol.status(), timeout=3.0, retries=2)
        if ok:
            await self._send(self.protocol.device_info(), timeout=3.0, retries=1)
            await self._send(self.protocol.time_sync(dt_util.now()), timeout=3.0, retries=1)

    async def _send(self, packet: bytearray, timeout: float = 5.0, retries: int = 2) -> bool:
        async with self._lock:
            for attempt in range(retries):
                if not self.client or not self.client.is_connected:
                    return False
                self._notification.clear()
                self._expected_response = self.protocol.command_key(packet)
                try:
                    await self.client.write_gatt_char(CHAR_UUID, packet, response=False)
                    await asyncio.wait_for(self._notification.wait(), timeout)
                    self._expected_response = None
                    return True
                except TimeoutError:
                    if attempt + 1 < retries:
                        await asyncio.sleep(0.2)
                except Exception:
                    _LOGGER.exception("Sunster BLE write failed")
                    break
        self._expected_response = None
        return False

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            await self._connect()
            if not await self._send(self.protocol.status(), timeout=4.0, retries=2):
                raise UpdateFailed("No status response from Sunster heater")
            self.data["connected"] = True
            return self.data
        except Exception as err:
            self.data["connected"] = False
            if self.client:
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
            self.client = None
            if isinstance(err, UpdateFailed):
                raise
            raise UpdateFailed(str(err)) from err

    async def _send_control(self, packet: bytearray, refresh: bool = True) -> None:
        await self._connect()
        if await self._send(packet, retries=2) and refresh:
            await self.async_request_refresh()

    async def turn_on(self) -> None:
        await self._send_control(self.protocol.power(True))

    async def turn_off(self) -> None:
        await self._send_control(self.protocol.power(False))

    async def set_temperature(self, temperature: int) -> None:
        minimum, maximum = ((46, 97) if self.data.get("temp_unit") == 1 else (8, 36))
        await self._send_control(self.protocol.set_temperature(max(minimum, min(maximum, temperature))), self.protocol.is_on)

    async def set_level(self, level: int) -> None:
        await self._send_control(self.protocol.set_level(max(1, min(10, level))), self.protocol.is_on)

    async def set_mode(self, mode: int) -> None:
        if mode not in self.data.get("available_modes", (1, 2)):
            raise ValueError(f"Unsupported Sunster mode {mode}")
        await self._send_control(self.protocol.set_mode(mode))

    async def set_setting(self, key: str, value: int | bool) -> None:
        await self._send_control(self.protocol.update_settings(**{key: value}))

    async def shutdown(self) -> None:
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None
