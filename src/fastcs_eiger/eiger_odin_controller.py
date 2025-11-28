import asyncio

from fastcs.connections import IPConnectionSettings

from fastcs_eiger.eiger_controller import EigerController
from fastcs_eiger.odin.odin_controller import OdinController


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
