from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from fastcs.attributes import AttributeIO, AttrR, AttrW
from fastcs.datatypes import DType_T
from fastcs.logging import bind_logger

from fastcs_eiger.eiger_parameter import EigerParameterRef
from fastcs_eiger.http_connection import HTTPConnection

FETCH_BEFORE_RETURNING = {"bit_depth_image", "bit_depth_readout"}


@dataclass
class EigerAttributeIO(AttributeIO[DType_T, EigerParameterRef]):
    """AttributeIO for ``EigerParameterRef`` Attributes"""

    def __init__(
        self,
        connection: HTTPConnection,
        update_now: Callable[[Sequence[str]], Awaitable[None]],
        queue_update: Callable[[Sequence[str]], Awaitable[None]],
    ):
        super().__init__()
        self.connection = connection
        self.update_now = update_now
        self.queue_update = queue_update
        self.logger = bind_logger(__class__.__name__)

        self.first_poll_complete = False

    def _handle_params_to_update(
        self, parameters: list[str], uri: str
    ) -> tuple[list[str], list[str]]:
        update_now = []
        update_later = []
        if not parameters:  # no response, queue update for the parameter we just put to
            update_later.append(uri.split("/", 4)[-1])
        else:
            for parameter in parameters:
                if parameter == "difference_mode":
                    # handling Eiger API inconsistency
                    parameter = "threshold/difference/mode"
                if parameter in FETCH_BEFORE_RETURNING:
                    update_now.append(parameter)
                else:
                    update_later.append(parameter)
        return update_now, update_later

    async def send(
        self, attr: AttrW[DType_T, EigerParameterRef], value: DType_T
    ) -> None:
        parameters_to_update = await self.connection.put(attr.io_ref.uri, value)
        update_now, update_later = self._handle_params_to_update(
            parameters_to_update, attr.io_ref.uri
        )

        self.logger.info(
            "Parameter put",
            attribute=attr,
            value=value,
            update_now=update_now,
            update_later=update_later,
        )

        await self.update_now(update_now)
        await self.queue_update(update_later)

    async def do_update(self, attr: AttrR[Any, EigerParameterRef]) -> None:
        try:
            response = await self.connection.get(attr.io_ref.uri)
            value = response["value"]
            if isinstance(value, list) and all(
                isinstance(s, str) for s in value
            ):  # error is a list of strings
                value = ", ".join(value)

            self.log_event(
                "Query for parameter",
                uri=attr.io_ref.uri,
                response=response,
                topic=attr,
            )

            await attr.update(value)
        except Exception as e:
            print(f"Failed to get {attr.io_ref.uri}:\n{e.__class__.__name__} {e}")

    async def update(self, attr: AttrR[DType_T, EigerParameterRef]) -> None:
        if attr.io_ref.mode == "config" and self.first_poll_complete:
            return
        await self.do_update(attr)
        self.first_poll_complete = True
