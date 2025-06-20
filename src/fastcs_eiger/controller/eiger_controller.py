import asyncio
import logging
from collections.abc import Coroutine, Iterable
from typing import Literal

from fastcs2 import AttributeR, AttributeRW, Controller

from fastcs_eiger.attribute_io import EIGER_IO_REFS
from fastcs_eiger.attribute_io.eiger_attribute_io import EigerAttributeIO
from fastcs_eiger.attribute_io.eiger_config_attribute_io import EigerConfigAttributeIO
from fastcs_eiger.attribute_io.internal_attribute_io import (
    InternalAttributeIO,
    InternalAttributeIORef,
)
from fastcs_eiger.eiger_parameter import (
    EIGER_PARAMETER_MODES,
    EigerParameter,
    EigerParameterResponse,
    key_to_attribute_name,
)
from fastcs_eiger.http_connection import HTTPConnection

# Keys to be ignored when introspecting the detector to create parameters
IGNORED_KEYS = [
    # Big arrays
    "countrate_correction_table",
    "pixel_mask",
    "threshold/1/pixel_mask",
    "threshold/2/pixel_mask",
    "flatfield",
    "threshold/1/flatfield",
    "threshold/2/flatfield",
    # Deprecated
    "board_000/th0_humidity",
    "board_000/th0_temp",
    # TODO: Value is [value, max], rather than using max metadata
    "buffer_fill_level",
    # TODO: Handle array values
    "detector_orientation",
    "detector_translation",
    # TODO: Is it a bad idea to include these?
    "test_image_mode",
    "test_image_value",
]

# Parameters that are in the API but missing from keys
MISSING_KEYS: dict[str, dict[str, list[str]]] = {
    "detector": {"status": ["error"], "config": ["wavelength"]},
    "monitor": {"status": [], "config": []},
    "stream": {"status": ["error"], "config": []},
}

FETCH_BEFORE_RETURNING = {"bit_depth_image", "bit_depth_readout"}


# def command_uri(key: str) -> str:
#     return f"detector/api/1.8.0/command/{key}"


# def detector_command(fn) -> Any:
#     return command(group="DetectorCommand")(fn)


# class EigerController(Controller):
#     """
#     Controller Class for Eiger Detector

#     Used for dynamic creation of variables useed in logic of the EigerFastCS backend.
#     Sets up all connections with the Simplon API to send and receive information
#     """

#     # Internal Attribute
#     stale_parameters = AttributeR("stale_parameters", bool)

#     def __init__(self, ip: str, port: int) -> None:
#         self._ip = ip
#         self._port = port
#         self.connection = HTTPConnection(self._ip, self._port)
#         # Parameter update logic
#         self._parameter_update_lock = asyncio.Lock()
#         self.queue = asyncio.Queue()

#         super().__init__(EigerAttributeIO(self.connection))

#     async def initialise(self) -> None:
#         """Create attributes by introspecting detector.

#         The detector will be initialized if it is not already.

#         """
#         self.connection.open()

#         try:
#             for subsystem in EIGER_PARAMETER_SUBSYSTEMS:
#                 match subsystem:
#                     case "detector":
#                         controller = EigerDetectorController(
#                             self.connection,
#                             self.queue_subsystem_update,
#                         )
#                         # detector subsystem initialises first
#                         # Check current state of detector_state to see
#                         # if initializing is required.
#                         state_val = await self.connection.get(
#                             "detector/api/1.8.0/status/state"
#                         )
#                         if state_val["value"] == "na":
#                             print("Initializing Detector")
#                             # send initialize command to detector
#                             await controller.initialize()
#                     case "monitor":
#                         controller = EigerMonitorController(
#                             self.connection,
#                             self.queue_subsystem_update,
#                         )
#                     case "stream":
#                         controller = EigerStreamController(
#                             self.connection,
#                             self.queue_subsystem_update,
#                         )
#                     case _:
#                         raise NotImplementedError(
#                             f"No subcontroller implemented for subsystem {subsystem}"
#                         )
#                 self.register_sub_controller(subsystem.capitalize(), controller)
#                 await controller.initialise()

#         except HTTPRequestError:
#             print("\nAn HTTP request failed while introspecting detector:\n")
#             raise

#     def get_subsystem_controllers(self) -> list["EigerSubsystemController"]:
#         return [
#             controller
#             for controller in self.get_sub_controllers().values()
#             if isinstance(controller, EigerSubsystemController)
#         ]

#     @scan(0.1)
#     async def update(self):
#         """Periodically check for parameters that need updating from the detector."""
#         if not self.queue.empty():
#             coros: list[Coroutine] = []
#             async with self._parameter_update_lock:
#                 while not self.queue.empty():
#                     coros.append(await self.queue.get())
#             await asyncio.gather(*coros)
#         self.stale_parameters._set(not self.queue.empty())

#     async def queue_subsystem_update(self, coros: list[Coroutine]):
#         if coros:
#             self.stale_parameters._set(True)
#             async with self._parameter_update_lock:
#                 for coro in coros:
#                     await self.queue.put(coro)
