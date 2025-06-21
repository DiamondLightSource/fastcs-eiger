import asyncio
from collections.abc import Coroutine

from fastcs2 import AttributeR, Controller

from fastcs_eiger.attribute_io.internal_attribute_io import (
    InternalAttributeIO,
    InternalAttributeIORef,
)
from fastcs_eiger.controller.eiger_detector_controller import EigerDetectorController
from fastcs_eiger.controller.eiger_monitor_controller import EigerMonitorController
from fastcs_eiger.controller.eiger_stream_controller import EigerStreamController
from fastcs_eiger.eiger_parameter import EIGER_PARAMETER_SUBSYSTEMS
from fastcs_eiger.http_connection import HTTPConnection, HTTPRequestError

# def command_uri(key: str) -> str:
#     return f"detector/api/1.8.0/command/{key}"


# def detector_command(fn) -> Any:
#     return command(group="DetectorCommand")(fn)


class EigerController(Controller):
    """
    Controller Class for Eiger Detector

    Used for dynamic creation of variables useed in logic of the EigerFastCS backend.
    Sets up all connections with the Simplon API to send and receive information
    """

    # Internal Attribute
    stale_parameters = AttributeR("stale_parameters", bool, InternalAttributeIORef())

    def __init__(self, ip: str, port: int) -> None:
        self._ip = ip
        self._port = port
        self.connection = HTTPConnection(self._ip, self._port)
        # Parameter update logic
        self._parameter_update_lock = asyncio.Lock()
        self.queue = asyncio.Queue()

        super().__init__([InternalAttributeIO()])

    async def initialise(self) -> None:
        """Create attributes by introspecting detector.

        The detector will be initialized if it is not already.

        """
        self.connection.open()

        try:
            for subsystem in EIGER_PARAMETER_SUBSYSTEMS:
                match subsystem:
                    case "detector":
                        controller = EigerDetectorController(
                            self.connection, self.queue_subsystem_update
                        )
                        # detector subsystem initialises first
                        # Check current state of detector_state to see
                        # if initializing is required.
                        state_val = await self.connection.get(
                            "detector/api/1.8.0/status/state"
                        )
                        if state_val["value"] == "na":
                            print("Initializing Detector")
                            # send initialize command to detector
                            # await controller.initialize()
                    case "monitor":
                        controller = EigerMonitorController(
                            self.connection, self.queue_subsystem_update
                        )
                    case "stream":
                        controller = EigerStreamController(
                            self.connection, self.queue_subsystem_update
                        )
                    case _:
                        raise NotImplementedError(
                            f"No subcontroller implemented for subsystem {subsystem}"
                        )
                self.register_sub_controller(subsystem, controller)
                await controller.initialise()

        except HTTPRequestError:
            print("\nAn HTTP request failed while introspecting detector:\n")
            raise

    async def queue_subsystem_update(self, coros: list[Coroutine[None, None, None]]):
        if coros:
            await self.stale_parameters.update(True)
            async with self._parameter_update_lock:
                for coro in coros:
                    await self.queue.put(coro)

    # @scan(0.1)
    async def update(self):
        """Periodically check for parameters that need updating from the detector."""
        if not self.queue.empty():
            coros: list[Coroutine] = []
            async with self._parameter_update_lock:
                while not self.queue.empty():
                    coros.append(await self.queue.get())
            await asyncio.gather(*coros)

        await self.stale_parameters.update(not self.queue.empty())
