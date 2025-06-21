from fastcs2 import AttributeRW

from fastcs_eiger.attribute_io.eiger_attribute_io import EigerAttributeIORef
from fastcs_eiger.attribute_io.internal_attribute_io import InternalAttributeIORef
from fastcs_eiger.controller.eiger_subsystem_controller import EigerSubsystemController


class EigerDetectorController(EigerSubsystemController):
    _subsystem = "detector"

    # Detector parameters to use in internal logic
    trigger_exposure = AttributeRW("trigger_exposure", float, InternalAttributeIORef())
    trigger_mode: AttributeRW[EigerAttributeIORef, str]

    # @detector_command
    # async def initialize(self):
    #     await self.connection.put(command_uri("initialize"))

    # @detector_command
    # async def arm(self):
    #     await self.connection.put(command_uri("arm"))

    # @detector_command
    # async def trigger(self):
    #     match self.trigger_mode.get(), self.trigger_exposure.get():
    #         case ("inte", exposure) if exposure > 0.0:
    #             await self.connection.put(command_uri("trigger"), exposure)
    #         case ("ints" | "inte", _):
    #             await self.connection.put(command_uri("trigger"))
    #         case _:
    #             raise RuntimeError("Can only do soft trigger in 'ints' or 'inte' mode")

    # @detector_command
    # async def disarm(self):
    #     await self.connection.put(command_uri("disarm"))

    # @detector_command
    # async def abort(self):
    #     await self.connection.put(command_uri("abort"))

    # @detector_command
    # async def cancel(self):
    #     await self.connection.put(command_uri("cancel"))
