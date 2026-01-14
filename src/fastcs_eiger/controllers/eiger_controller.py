import asyncio
from collections.abc import Coroutine

from fastcs.attributes import AttrR
from fastcs.connections import IPConnectionSettings
from fastcs.controllers import Controller
from fastcs.datatypes import Bool
from fastcs.logging import bind_logger
from fastcs.methods import command, scan

from fastcs_eiger.controllers.eiger_detector_controller import EigerDetectorController
from fastcs_eiger.controllers.eiger_monitor_controller import EigerMonitorController
from fastcs_eiger.controllers.eiger_stream_controller import EigerStreamController
from fastcs_eiger.controllers.eiger_subsystem_controller import EigerSubsystemController
from fastcs_eiger.eiger_parameter import EIGER_PARAMETER_SUBSYSTEMS
from fastcs_eiger.http_connection import HTTPConnection, HTTPRequestError


class EigerController(Controller):
    """Root controller for Eiger detectors

    Args:
        ip: IP address of Eiger detector
        port: Port of Eiger detector
    """

    detector: EigerDetectorController

    # Internal Attribute
    stale_parameters = AttrR(Bool())

    def __init__(self, connection_settings: IPConnectionSettings) -> None:
        super().__init__()
        self.connection_settings = connection_settings

        self.logger = bind_logger(__class__.__name__)

        self.connection = HTTPConnection(connection_settings)
        self._parameter_update_lock = asyncio.Lock()
        self.queue = asyncio.Queue()

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
                            self.connection,
                            self.queue_subsystem_update,
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
                            await controller.initialize()
                    case "monitor":
                        controller = EigerMonitorController(
                            self.connection,
                            self.queue_subsystem_update,
                        )
                    case "stream":
                        controller = EigerStreamController(
                            self.connection,
                            self.queue_subsystem_update,
                        )
                    case _:
                        raise NotImplementedError(
                            f"No subcontroller implemented for subsystem {subsystem}"
                        )
                self.add_sub_controller(subsystem, controller)
                await controller.initialise()

        except HTTPRequestError:
            print("\nAn HTTP request failed while introspecting detector:\n")
            raise

    def get_subsystem_controllers(self) -> list["EigerSubsystemController"]:
        return [
            controller
            for controller in self.sub_controllers.values()
            if isinstance(controller, EigerSubsystemController)
        ]

    @scan(0.1)
    async def update(self):
        """Periodically check for parameters that need updating from the detector."""
        if self.queue.empty():
            return

        coros: list[Coroutine] = []
        async with self._parameter_update_lock:
            while not self.queue.empty():
                coros.append(await self.queue.get())

        await asyncio.gather(*coros)

        if self.queue.empty():
            self.logger.info("All parameters updated")
            await self.stale_parameters.update(not self.queue.empty())

    async def queue_subsystem_update(self, coros: list[Coroutine]):
        if coros:
            await self.stale_parameters.update(True)
            async with self._parameter_update_lock:
                for coro in coros:
                    await self.queue.put(coro)

    @command()
    async def arm_when_ready(self):
        """Arm detector and return when ready to send triggers

        Wait for parmeters to be synchronised before arming detector

        Raises:
            TimeoutError: If parameters are not synchronised or arm PUT request fails

        """
        await self.stale_parameters.wait_for_value(False, timeout=1)
        await self.detector.arm()
