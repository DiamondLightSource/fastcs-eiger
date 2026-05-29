import asyncio
from dataclasses import dataclass

from fastcs.attributes import AttrRW
from fastcs.connections import IPConnectionSettings
from fastcs.datatypes import Bool, Int
from fastcs.methods import command

from fastcs_eiger.controllers.eiger_controller import (
    COMMAND_GROUP,
    EigerController,
    EigerControllerSettings,
)
from fastcs_eiger.controllers.odin.odin_controller import OdinController


@dataclass
class EigerOdinControllerSettings(EigerControllerSettings):
    odin_connection_settings: IPConnectionSettings


class EigerOdinController(EigerController):
    """Eiger controller with Odin sub controller"""

    start_writing_timeout = AttrRW(
        Int(min=1),
        initial_value=5,
        description="Timeout for start writing command",
        group=COMMAND_GROUP,
    )
    enable_vds_creation = AttrRW(Bool())

    def __init__(self, settings: EigerOdinControllerSettings) -> None:
        super().__init__(
            EigerControllerSettings(settings.connection_settings, settings.api_version)
        )

        self.OD = OdinController(settings.odin_connection_settings)

    async def initialise(self) -> None:
        """Initialise eiger controller and odin controller"""

        await asyncio.gather(super().initialise(), self.OD.initialise())

    @command(group=COMMAND_GROUP)
    async def arm_when_ready(self):
        """Check eiger fan is ready before reporting arm as successful

        Raises:
            TimeoutError: If eiger fan is not ready

        """
        await super().arm_when_ready()

        try:
            await self.OD.EF.ready.wait_for_value(True, timeout=self.arm_timeout.get())
        except TimeoutError as e:
            raise TimeoutError("Eiger fan not ready") from e

    @command(group=COMMAND_GROUP)
    async def start_writing(self):
        """Sync eiger parameters to file writers, start writing and return when ready

        Raises:
            TimeoutError: If file writers fail to start

        """
        await asyncio.gather(
            self.OD.FP.data_compression.put(self.detector.compression.get().upper()),
            self.OD.FP.data_datatype.put(f"uint{self.detector.bit_depth_image.get()}"),
        )

        await self.OD.FP.start_writing()

        try:
            await self.OD.writing.wait_for_value(
                True, timeout=self.start_writing_timeout.get()
            )
        except TimeoutError as e:
            raise TimeoutError("File writers failed to start") from e
