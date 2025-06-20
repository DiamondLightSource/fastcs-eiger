import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from fastcs2.attribute import AttributeR, AttributeRW
from fastcs2.datatypes import DataType

from fastcs_eiger.attribute_io.eiger_attribute_io import (
    EigerAttributeIO,
    EigerAttributeIORef,
)
from fastcs_eiger.http_connection import HTTPConnection


@dataclass
class EigerConfigAttributeIORef(EigerAttributeIORef):
    mode = "config"


class EigerConfigAttributeIO(EigerAttributeIO):
    """Handler for config parameters that are polled once on startup."""

    first_poll_complete: bool = False

    def __init__(
        self,
        connection: HTTPConnection,
        handle_update_fn: Callable[[str, list[str]], Coroutine[None, None, None]],
    ):
        super().__init__(connection, handle_update_fn, EigerConfigAttributeIORef)

    async def update(self, attr: AttributeR) -> None:
        # Only poll once on startup
        if not self.first_poll_complete:
            await super().update(attr)
            # if isinstance(attr, AttributeRW):
            #     # Sync readback value to demand
            #     await attr.publish(attr.get())

            self.first_poll_complete = True

    async def config_update(self, attr: AttributeR) -> None:
        await super().update(attr)

    async def send(
        self, attr: AttributeRW[EigerAttributeIORef, DataType], value: Any
    ) -> None:
        logging.info(f"Sending {value} to {attr.io_ref.uri}")
        parameters_to_update = await self._connection.put(attr.io_ref.uri, value)
        await self._handle_update(attr.io_ref.key, parameters_to_update)
        logging.info("Put complete")
