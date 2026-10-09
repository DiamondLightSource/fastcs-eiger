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

    # EF endpoint information
    endpoints_0_ip_address: AttrR[str]
    endpoints_0_port: AttrR[int]

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
        socket.setsockopt(zmq.LINGER, 1000)
        full_address = (
            f"tcp://{self.endpoints_0_ip_address.get()}:{self.endpoints_0_port.get()}"
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
            if socket.poll(2000):
                reply = socket.recv_string()
                logger.info("EigerFan restart response: %s", reply)
            else:
                logger.warning("No response from EigerFan restart command")
        except Exception:
            logger.opt(exception=True).warning(
                "Failed to restart Eiger FAN",
            )
        finally:
            socket.disconnect(full_address)
            socket.close()
            ctx.term()
