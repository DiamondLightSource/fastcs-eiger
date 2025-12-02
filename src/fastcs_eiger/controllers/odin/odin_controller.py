from fastcs.attributes import AttrR
from fastcs.controllers import BaseController
from fastcs.datatypes import Bool
from fastcs_odin.controllers import OdinController as _OdinController
from fastcs_odin.http_connection import HTTPConnection
from fastcs_odin.io import StatusSummaryAttributeIORef
from fastcs_odin.util import OdinParameter

from fastcs_eiger.controllers.odin.eiger_fan import EigerFanAdapterController


class OdinController(_OdinController):
    """Eiger-specific Odin controller"""

    writing: AttrR = AttrR(
        Bool(), io_ref=StatusSummaryAttributeIORef([("MW", "FP")], "writing", any)
    )

    def _create_adapter_controller(
        self,
        connection: HTTPConnection,
        parameters: list[OdinParameter],
        adapter: str,
        module: str,
    ) -> BaseController:
        """Create Eiger-specific adapter controllers."""

        match module:
            case "EigerFanAdapter":
                return EigerFanAdapterController(
                    connection, parameters, f"{self.API_PREFIX}/{adapter}", self._ios
                )
            case _:
                return super()._create_adapter_controller(
                    connection, parameters, adapter, module
                )
