import asyncio

from fastcs.connections import IPConnectionSettings

from fastcs_eiger.controllers.eiger_controller import EigerController
from fastcs_eiger.controllers.odin.odin_controller import OdinController
from fastcs_eiger.eiger_parameter import EigerAPIVersion


class EigerOdinController(EigerController):
    """Eiger controller with Odin sub controller"""

    def __init__(
        self,
        detector_connection_settings: IPConnectionSettings,
        odin_connection_settings: IPConnectionSettings,
        api_version: EigerAPIVersion,
    ) -> None:
        super().__init__(detector_connection_settings, api_version)

        self.OD = OdinController(odin_connection_settings)

    async def initialise(self) -> None:
        """Initialise eiger controller and odin controller"""

        await asyncio.gather(super().initialise(), self.OD.initialise())
