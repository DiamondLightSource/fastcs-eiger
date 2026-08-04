import datetime
import json

import zmq
from fastcs.attributes import AttrR, AttrRW
from fastcs.datatypes import Bool
from fastcs.logging import logger
from fastcs.methods import command
from fastcs_odin.controllers import OdinSubController
from fastcs_odin.io import StatusSummaryAttributeIORef
from fastcs_odin.util import create_attribute


class EigerFanAdapterController(OdinSubController):
    """Controller for an EigerFan adapter in an odin control server"""

    state: AttrR[str]
    acqid: AttrRW[str]
    block_size: AttrRW[int]
    ready: AttrR[bool]

    # Control channel information
    eiger_channel_address: AttrRW[str]
    ctrl_channel_port: AttrRW[str]

    async def initialise(self):
        for parameter in self.parameters:
            # Remove 0 index and status/config
            match parameter.uri:
                case ["0", "status" | "config", *_]:
                    parameter.set_path(parameter.path[2:])
            self.add_attribute(
                parameter.name,
                create_attribute(parameter=parameter, api_prefix=self._api_prefix),
            )

        # Manually validate `state` to get a nicer error message if not introspected
        self._validate_hinted_attribute("state")

        self.ready = AttrR(
            Bool(),
            io_ref=StatusSummaryAttributeIORef(
                [], "", lambda states: states[0] == "DSTR_HEADER", [self.state]
            ),
        )

    @command()
    async def restart(self):
        logger.info("Restarting Eiger FAN...")
        ctx = zmq.Context()
        socket = ctx.socket(zmq.DEALER)
        full_address = (
            f"tcp://{self.eiger_channel_address.get()}:{self.ctrl_channel_port.get()}"
        )
        msg = {
            "msg_type": "cmd",
            "id": 1,
            "msg_val": "configure",
            "params": {"restart": True},
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
        try:
            socket.connect(full_address)
            socket.send_string(json.dumps(msg))
        except Exception:
            logger.opt(exception=True).warning(
                "Failed to restart Eiger FAN",
            )
        finally:
            socket.disconnect(full_address)
