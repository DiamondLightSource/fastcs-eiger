from fastcs.attributes import AttrR, AttrRW
from fastcs_odin.controllers.odin_data.frame_processor import (
    FrameProcessorAdapterController,
)


class EigerFrameProcessorAdapterController(FrameProcessorAdapterController):
    data_compression: AttrRW[str]
    data_datatype: AttrRW[str]
    data_dims_0: AttrR[int]  # y
    data_dims_1: AttrR[int]  # x
