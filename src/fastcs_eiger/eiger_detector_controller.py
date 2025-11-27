from typing import Any

from fastcs.attributes import AttrR, AttrRW
from fastcs.datatypes import Float
from fastcs.methods import command

from fastcs_eiger.eiger_subsystem_controller import EigerSubsystemController


def command_uri(key: str) -> str:
    return f"detector/api/1.8.0/command/{key}"


def detector_command(fn) -> Any:
    return command(group="DetectorCommand")(fn)


class EigerDetectorController(EigerSubsystemController):
    _subsystem = "detector"

    # Internal attribute to control triggers in `inte` mode
    trigger_exposure = AttrRW(Float())
    # Introspected attribute needed for trigger logic
    trigger_mode: AttrR[str]

    @detector_command
    async def initialize(self):
        await self.connection.put(command_uri("initialize"))

    @detector_command
    async def arm(self):
        await self.connection.put(command_uri("arm"))

    @detector_command
    async def trigger(self):
        match self.trigger_mode.get(), self.trigger_exposure.get():
            case ("inte", exposure) if exposure > 0.0:
                await self.connection.put(command_uri("trigger"), exposure)
            case ("ints" | "inte", _):
                await self.connection.put(command_uri("trigger"))
            case _:
                raise RuntimeError("Can only do soft trigger in 'ints' or 'inte' mode")

    @detector_command
    async def disarm(self):
        await self.connection.put(command_uri("disarm"))

    @detector_command
    async def abort(self):
        await self.connection.put(command_uri("abort"))

    @detector_command
    async def cancel(self):
        await self.connection.put(command_uri("cancel"))
