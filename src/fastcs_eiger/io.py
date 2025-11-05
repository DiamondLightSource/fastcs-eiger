from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from fastcs.attribute_io import AttributeIO
from fastcs.attributes import AttrR, AttrW
from fastcs.datatypes import T

from fastcs_eiger.eiger_parameter import EigerParameterRef
from fastcs_eiger.http_connection import HTTPConnection

FETCH_BEFORE_RETURNING = {"bit_depth_image", "bit_depth_readout"}


@dataclass
class EigerAttributeIO(AttributeIO[T, EigerParameterRef]):
    """
    Handler for FastCS Attribute Creation

    Dataclass that is called using the AttrR, AttrRW function.
    Handler uses uri of detector to collect data for PVs
    """

    connection: HTTPConnection
    update_now: Callable[[Sequence[str]], Awaitable[None]]
    queue_update: Callable[[Sequence[str]], Awaitable[None]]
    first_poll_complete: bool = False

    def _handle_params_to_update(self, parameters: list[str], uri: str):
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

    async def send(self, attr: AttrW[T, EigerParameterRef], value: T) -> None:
        parameters_to_update = await self.connection.put(attr.io_ref.uri, value)
        update_now, update_later = self._handle_params_to_update(
            parameters_to_update, attr.io_ref.uri
        )
        await self.update_now(update_now)
        print(
            f"Queueing updates for parameters after setting {attr.io_ref.uri}: "
            f"{update_later}"
        )
        await self.queue_update(update_later)

    async def do_update(self, attr: AttrR[T, EigerParameterRef]) -> None:
        try:
            response = await self.connection.get(attr.io_ref.uri)
            value = response["value"]
            if isinstance(value, list) and all(
                isinstance(s, str) for s in value
            ):  # error is a list of strings
                value = ", ".join(value)
            await attr.update(value)
        except Exception as e:
            print(f"Failed to get {attr.io_ref.uri}:\n{e.__class__.__name__} {e}")

    async def update(self, attr: AttrR[T, EigerParameterRef]) -> None:
        if attr.io_ref.mode == "config" and self.first_poll_complete:
            return
        await self.do_update(attr)
        self.first_poll_complete = True
