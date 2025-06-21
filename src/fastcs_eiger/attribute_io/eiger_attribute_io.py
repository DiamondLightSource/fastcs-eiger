import logging
from collections.abc import Callable, Coroutine
from dataclasses import KW_ONLY, dataclass
from typing import Any

from fastcs2.attribute import AttributeR, AttributeRW
from fastcs2.attribute_io import AttributeIO
from fastcs2.attribute_io_ref import AttributeIORef
from fastcs2.datatypes import DataType

from fastcs_eiger.http_connection import HTTPConnection


@dataclass
class EigerAttributeIORef(AttributeIORef):
    subsystem: str
    mode: str
    key: str
    _: KW_ONLY
    update_period: float | None = 0.2

    @property
    def uri(self) -> str:
        """Full URI for HTTP requests."""
        return f"{self.subsystem}/api/1.8.0/{self.mode}/{self.key}"


class EigerAttributeIO(AttributeIO):
    """
    Handler for FastCS Attribute Creation

    Dataclass that is called using the AttrR, AttrRW function.
    Handler uses uri of detector to collect data for PVs
    """

    first_poll_complete: bool = False

    def __init__(
        self,
        connection: HTTPConnection,
        handle_update_fn: Callable[[str, list[str]], Coroutine[None, None, None]],
        io_ref: type[EigerAttributeIORef] = EigerAttributeIORef,
    ):
        self._connection = connection
        self._handle_update = handle_update_fn

        super().__init__(io_ref)

    async def _update(self, attr: AttributeR[EigerAttributeIORef, DataType]) -> None:
        try:
            response = await self._connection.get(attr.io_ref.uri)
            value = response["value"]
            if isinstance(value, list) and all(
                isinstance(s, str) for s in value
            ):  # error is a list of strings
                value = ", ".join(value)
            await attr.update(value)
        except Exception as e:
            print(f"Failed to get {attr.io_ref.uri}:\n{e.__class__.__name__} {e}")

    async def update(self, attr: AttributeR) -> None:
        # Only poll once on startup
        if attr.io_ref.mode == "config" and self.first_poll_complete:
            return

        await self._update(attr)
        # if isinstance(attr, AttributeRW):
        #     # Sync readback value to demand
        #     await attr.publish(attr.get())

        self.first_poll_complete = True

    async def config_update(self, attr: AttributeR) -> None:
        await self._update(attr)

    async def send(
        self, attr: AttributeRW[EigerAttributeIORef, DataType], value: Any
    ) -> None:
        logging.info(f"Sending {value} to {attr.io_ref.uri}")
        parameters_to_update = await self._connection.put(attr.io_ref.uri, value)
        await self._handle_update(attr.io_ref.key, parameters_to_update)
        logging.info("Put complete")
