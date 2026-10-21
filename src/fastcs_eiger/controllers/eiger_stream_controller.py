import asyncio

from fastcs.attributes import AttrRW
from fastcs.methods.scan import scan
from fastcs.util import ONCE

from fastcs_eiger.controllers.eiger_subsystem_controller import EigerSubsystemController


class EigerStreamController(EigerSubsystemController):
    mode: AttrRW[bool]
    format: AttrRW[str]
    header_detail: AttrRW[str]

    _subsystem = "stream"

    @scan(period=ONCE)
    async def set_stream_config(self):
        await asyncio.gather(
            self.mode.put(True, sync_setpoint=True),
            self.format.put("cbor", sync_setpoint=True),
            self.header_detail.put("all", sync_setpoint=True),
        )
