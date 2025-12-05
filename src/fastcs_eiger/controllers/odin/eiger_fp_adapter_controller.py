from fastcs.attributes import AttrRW
from fastcs_odin.controllers.odin_data.frame_processor import (
    FrameProcessorAdapterController,
)


class EigerFrameProcessorAdapterController(FrameProcessorAdapterController):
    data_compression: AttrRW[str]
    data_datatype: AttrRW[str]
