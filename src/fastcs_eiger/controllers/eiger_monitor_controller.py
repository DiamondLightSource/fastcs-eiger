from io import BytesIO

import numpy as np
from fastcs.attributes import AttrR
from fastcs.datatypes import Waveform
from fastcs.methods import scan
from PIL import Image

from fastcs_eiger.controllers.eiger_subsystem_controller import EigerSubsystemController

DEFAULT_IMAGE_SHAPE = (5000, 5000)
DEFAULT_IMAGE = np.array(range(np.prod(DEFAULT_IMAGE_SHAPE)), dtype=np.uint32).reshape(
    *DEFAULT_IMAGE_SHAPE
)


class EigerMonitorController(EigerSubsystemController):
    _subsystem = "monitor"

    image = AttrR(
        Waveform(np.uint32, shape=DEFAULT_IMAGE_SHAPE), initial_value=DEFAULT_IMAGE
    )
    line = AttrR(Waveform(np.float64, shape=(10,)), initial_value=np.sin(np.arange(10)))

    @scan(1)
    async def handle_monitor(self):
        """Poll monitor images to display."""
        if (image := await self._read_monitor_image()) is not None:
            await self.image.update(image)

    async def _read_monitor_image(self) -> np.ndarray | None:
        response, image_bytes = await self.connection.get_bytes(
            "monitor/api/1.8.0/images/next"
        )

        if response.status == 200:
            return np.array(Image.open(BytesIO(image_bytes)).getdata())
