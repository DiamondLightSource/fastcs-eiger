import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from enum import IntEnum

from fastcs.attributes import AttrR, AttrRW
from fastcs.connections import IPConnectionSettings
from fastcs.controllers import Controller
from fastcs.datatypes import Bool, Enum, Int, String
from fastcs.logging import logger
from fastcs.methods import command, scan

from fastcs_eiger.controllers.eiger_detector_controller import EigerDetectorController
from fastcs_eiger.controllers.eiger_monitor_controller import EigerMonitorController
from fastcs_eiger.controllers.eiger_stream_controller import EigerStreamController
from fastcs_eiger.controllers.eiger_subsystem_controller import EigerSubsystemController
from fastcs_eiger.eiger_parameter import EIGER_PARAMETER_SUBSYSTEMS, EigerAPIVersion
from fastcs_eiger.http_connection import HTTPConnection, HTTPRequestError

COMMAND_GROUP = "Command"

GDA_GROUP = "GDA"


class CaptureEnum(IntEnum):
    """Enum for datatype attribute"""

    Idle = 0
    Active = 1


class DatatpyeEnum(IntEnum):
    """Enum for datatype attribute"""

    UInt8 = 0
    UInt16 = 1
    UInt32 = 2
    UInt64 = 3


class ImageModeEnum(IntEnum):
    """Enum for image mode attribute"""

    Single = 0
    Multiple = 1
    Continuous = 2


class TriggerModeEnum(IntEnum):
    """Enum for trigger mode attribute"""

    Internal_Series = 0
    Internal_Enable = 1
    External_Series = 2
    External_Enable = 3


@dataclass
class EigerControllerSettings:
    connection_settings: IPConnectionSettings
    api_version: EigerAPIVersion


class EigerController(Controller):
    """Root controller for Eiger detectors

    Args:
        ip: IP address of Eiger detector
        port: Port of Eiger detector
    """

    detector: EigerDetectorController

    # Soft signals for GDA
    image_mode = AttrRW(Enum(enum_cls=ImageModeEnum), group=GDA_GROUP)
    trigger_mode = AttrRW(Enum(enum_cls=TriggerModeEnum), group=GDA_GROUP)
    manual_trigger = AttrRW(String(), initial_value="No", group=GDA_GROUP)
    start_timeout = AttrRW(Bool(), group=GDA_GROUP)
    datatype = AttrRW(Enum(enum_cls=DatatpyeEnum), group=GDA_GROUP)
    clear_errors = AttrRW(Bool(), group=GDA_GROUP)
    close_file_timeout = AttrRW(Int(min=1), initial_value=3, group=GDA_GROUP)
    # Internal Attributes

    stale_parameters = AttrR(Bool())
    arm_timeout = AttrRW(
        Int(min=1),
        initial_value=3,
        description="Timeout for arm command",
        group=COMMAND_GROUP,
    )

    def __init__(self, settings: EigerControllerSettings) -> None:
        super().__init__()
        self.connection_settings = settings.connection_settings

        self.connection = HTTPConnection(settings.connection_settings)
        self._parameter_update_lock = asyncio.Lock()
        self.queue = asyncio.Queue()
        self._api_version: EigerAPIVersion = settings.api_version

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
                            self._api_version,
                        )
                        # detector subsystem initialises first
                        # Check current state of detector_state to see
                        # if initializing is required.
                        state_val = await self.connection.get(
                            f"detector/api/{self._api_version}/status/state"
                        )
                        if state_val["value"] == "na":
                            print("Initializing Detector")
                            # send initialize command to detector
                            await controller.initialize()
                    case "monitor":
                        controller = EigerMonitorController(
                            self.connection,
                            self.queue_subsystem_update,
                            self._api_version,
                        )
                    case "stream":
                        controller = EigerStreamController(
                            self.connection,
                            self.queue_subsystem_update,
                            self._api_version,
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
            logger.info("All parameters updated")
            await self.stale_parameters.update(not self.queue.empty())

    async def queue_subsystem_update(self, coros: list[Coroutine]):
        if coros:
            await self.stale_parameters.update(True)
            async with self._parameter_update_lock:
                for coro in coros:
                    await self.queue.put(coro)

    @command(group=COMMAND_GROUP)
    async def arm_when_ready(self):
        """Arm detector and return when ready to send triggers

        Wait for parmeters to be synchronised before arming detector

        Raises:
            TimeoutError: If parameters are not synchronised or arm PUT request fails

        """
        await self.stale_parameters.wait_for_value(
            False, timeout=self.arm_timeout.get()
        )

        await self.detector.arm()
