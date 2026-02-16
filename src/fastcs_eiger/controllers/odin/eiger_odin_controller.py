import asyncio

from fastcs.connections import IPConnectionSettings
from fastcs.methods import command

from fastcs_eiger.controllers.eiger_controller import EigerController
from fastcs_eiger.controllers.odin.odin_controller import OdinController


class EigerOdinController(EigerController):
    """Eiger controller with Odin sub controller"""

    def __init__(
        self,
        detector_connection_settings: IPConnectionSettings,
        odin_connection_settings: IPConnectionSettings,
    ) -> None:
        super().__init__(detector_connection_settings)

        self.OD = OdinController(odin_connection_settings)

    async def initialise(self) -> None:
        """Initialise eiger controller and odin controller"""

        await asyncio.gather(super().initialise(), self.OD.initialise())

    @command()
    async def arm_when_ready(self):
        """Check eiger fan is ready before reporting arm as successful

        Raises:
            TimeoutError: If eiger fan is not ready

        """
        await super().arm_when_ready()

        try:
            await self.OD.EF.ready.wait_for_value(True, timeout=3)
        except TimeoutError as e:
            raise TimeoutError("Eiger fan not ready") from e

    @command()
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
            await self.OD.writing.wait_for_value(True, timeout=3)
        except TimeoutError as e:
            raise TimeoutError("File writers failed to start") from e
