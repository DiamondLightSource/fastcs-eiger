from fastcs.attributes import AttrR, AttrRW
from fastcs.controllers import BaseController
from fastcs.datatypes import Bool, Int, String
from fastcs_odin.controllers import OdinController as _OdinController
from fastcs_odin.controllers.odin_data.meta_writer import MetaWriterAdapterController
from fastcs_odin.http_connection import HTTPConnection
from fastcs_odin.io import StatusSummaryAttributeIORef
from fastcs_odin.io.config_fan_sender_attribute_io import ConfigFanAttributeIORef
from fastcs_odin.util import OdinParameter

from fastcs_eiger.controllers.odin.eiger_fan import EigerFanAdapterController
from fastcs_eiger.controllers.odin.eiger_fp_adapter_controller import (
    EigerFrameProcessorAdapterController,
)


class OdinController(_OdinController):
    """Eiger-specific Odin controller"""

    FP: EigerFrameProcessorAdapterController
    EF: EigerFanAdapterController
    MW: MetaWriterAdapterController

    writing = AttrR(
        Bool(), io_ref=StatusSummaryAttributeIORef([("MW", "FP")], "writing", any)
    )

    async def initialise(self):
        await super().initialise()

        self.file_path = AttrRW(
            String(),
            io_ref=ConfigFanAttributeIORef([self.FP.file_path, self.MW.directory]),
        )
        self.file_prefix = AttrRW(
            String(),
            io_ref=ConfigFanAttributeIORef([self.FP.file_prefix, self.MW.file_prefix]),
        )
        self.acquisition_id = AttrRW(
            String(),
            io_ref=ConfigFanAttributeIORef(
                [
                    self.file_prefix,
                    self.FP.acquisition_id,
                    self.MW.acquisition_id,
                    self.EF.acqid,
                ]
            ),
        )
        self.block_size = AttrRW(
            Int(),
            io_ref=ConfigFanAttributeIORef(
                [self.FP.process_frames_per_block, self.EF.block_size]
            ),
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
            case "FrameProcessorAdapter":
                return EigerFrameProcessorAdapterController(
                    connection, parameters, f"{self.API_PREFIX}/{adapter}", self._ios
                )
            case "EigerFanAdapter":
                return EigerFanAdapterController(
                    connection, parameters, f"{self.API_PREFIX}/{adapter}", self._ios
                )
            case _:
                return super()._create_adapter_controller(
                    connection, parameters, adapter, module
                )
