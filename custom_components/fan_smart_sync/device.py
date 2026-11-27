"""Bluetooth connection to one fan. Uses bleak only, with no Home Assistant imports."""

from __future__ import annotations

import asyncio
import logging

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from . import protocol
from .protocol import Status

_LOGGER = logging.getLogger(__name__)

REPLY_TIMEOUT = 5.0
# The fan takes one connection at a time. Letting go when idle leaves room for the phone app.
IDLE_DISCONNECT = 15.0
# Upper bound for one connect-and-read attempt. Each operation makes at most two attempts.
ATTEMPT_TIMEOUT = 30.0


def _describe(err: BaseException) -> str:
    text = str(err).strip()
    return f"{type(err).__name__}: {text}" if text else type(err).__name__


class FanError(Exception):
    """The fan couldn't be reached or didn't answer."""


class FanSmartSyncDevice:
    def __init__(self, ble_device: BLEDevice) -> None:
        self._ble_device = ble_device
        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()
        self._reply: asyncio.Future[tuple[int, bytes]] | None = None
        self._idle: asyncio.TimerHandle | None = None
        self.status: Status | None = None
        self._stage = "connecting"

    @property
    def address(self) -> str:
        return self._ble_device.address

    def set_ble_device(self, ble_device: BLEDevice) -> None:
        """Use the newest advertisement (it may arrive through a different adapter or proxy)."""
        self._ble_device = ble_device

    # ----- public operations -----
    async def update(self) -> Status:
        return await self._run(None)

    async def set_speed(self, speed: int) -> Status:
        return await self._run(protocol.fan_command(speed))

    async def set_light(self, on: bool, percent: int) -> Status:
        return await self._run(protocol.light_command(on, percent))

    async def disconnect(self) -> None:
        async with self._lock:
            await self._disconnect()

    # ----- internals -----
    async def _run(self, command: bytes | None) -> Status:
        async with self._lock:
            for attempt in (1, 2):
                self._stage = "connecting"
                try:
                    # One cap for the whole attempt, so a fan that never answers can't stall Home Assistant.
                    async with asyncio.timeout(ATTEMPT_TIMEOUT):
                        await self._connect()
                        if command is not None:
                            self._stage = "sending the command"
                            kind, _ = await self._request(command)
                            if kind != protocol.KIND_ACK:
                                _LOGGER.debug("%s: command answered with %02x", self.address, kind)
                        self._stage = "reading status"
                        kind, body = await self._request(protocol.status_request())
                        if kind != protocol.KIND_STATUS:
                            raise FanError(f"unexpected reply {kind:02x} to a status request")
                    self.status = protocol.parse_status(body)
                    self._schedule_idle()
                    return self.status
                except (BleakError, TimeoutError, protocol.FrameError, FanError) as err:
                    await self._disconnect()
                    reason = _describe(err)
                    if isinstance(err, TimeoutError):
                        reason = f"no answer within {ATTEMPT_TIMEOUT:.0f} s"
                    if attempt == 2:
                        raise FanError(f"{reason} while {self._stage}") from err
                    _LOGGER.debug("%s: attempt 1 failed while %s (%s), retrying", self.address, self._stage, reason)
        raise AssertionError("unreachable")

    async def _connect(self) -> None:
        if self._client and self._client.is_connected:
            return
        _LOGGER.debug("%s: connecting", self.address)
        client = await establish_connection(
            BleakClientWithServiceCache,
            self._ble_device,
            self._ble_device.name or self.address,
            max_attempts=2,
            disconnected_callback=self._on_disconnect,
            ble_device_callback=lambda: self._ble_device,
        )
        self._stage = "subscribing to replies"
        try:
            await client.start_notify(protocol.NOTIFY_UUID, self._on_notify)
        except BaseException:
            await client.disconnect()
            raise
        self._client = client

    async def _request(self, data: bytes) -> tuple[int, bytes]:
        assert self._client is not None
        self._reply = asyncio.get_running_loop().create_future()
        try:
            await self._client.write_gatt_char(protocol.WRITE_UUID, data, response=True)
            try:
                async with asyncio.timeout(REPLY_TIMEOUT):
                    return await self._reply
            except TimeoutError:
                raise FanError(f"no reply within {REPLY_TIMEOUT:.0f} s") from None
        finally:
            self._reply = None

    def _on_notify(self, _char: object, data: bytearray) -> None:
        try:
            kind, body = protocol.parse(bytes(data))
        except protocol.FrameError as err:
            _LOGGER.debug("%s: ignoring %s", self.address, err)
            return
        if self._reply and not self._reply.done():
            self._reply.set_result((kind, body))

    def _schedule_idle(self) -> None:
        if self._idle:
            self._idle.cancel()
        loop = asyncio.get_running_loop()
        self._idle = loop.call_later(IDLE_DISCONNECT, lambda: loop.create_task(self.disconnect()))

    def _on_disconnect(self, _client: object) -> None:
        _LOGGER.debug("%s: disconnected", self.address)
        if self._reply and not self._reply.done():
            self._reply.set_exception(FanError("disconnected"))

    async def _disconnect(self) -> None:
        if self._idle:
            self._idle.cancel()
            self._idle = None
        client, self._client = self._client, None
        if client:
            try:
                await client.disconnect()
            except BleakError:
                pass
