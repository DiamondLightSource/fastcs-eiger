import asyncio
from io import BytesIO

import numpy as np
from fastcs.attributes import AttrR, AttrRW
from fastcs.datatypes import Int, Waveform
from fastcs.methods import scan
from PIL import Image

from fastcs_eiger.controllers.eiger_subsystem_controller import EigerSubsystemController

BIT_DEPTH_TO_DTYPE = {8: np.uint8, 16: np.uint16, 32: np.uint32}


class EigerMonitorController(EigerSubsystemController):
    _subsystem = "monitor"

    mode: AttrRW[bool]

    async def _detector_config(self, key: str):
        """Value of a detector config parameter.

        The equivalent ``Attribute`` on the detector sub controller does not have a
        value yet - introspected ``AttrR``s are not updated until after every
        controller has been initialised - so the value is fetched directly.

        Args:
            key: Key of the parameter within the detector config

        """
        response = await self.connection.get(
            f"detector/api/{self._api_version}/config/{key}"
        )
        return response["value"]

    async def initialise(self) -> None:
        await super().initialise()

        await self.mode.put(True)

        width, height, bit_depth = await asyncio.gather(
            self._detector_config("x_pixels_in_detector"),
            self._detector_config("y_pixels_in_detector"),
            self._detector_config("bit_depth_image"),
        )

        self.image = AttrR(
            Waveform(BIT_DEPTH_TO_DTYPE[bit_depth], shape=(height, width))
        )
        self.image_max = AttrRW(Int(), initial_value=100)
        self.image_min = AttrRW(Int(), initial_value=0)

    @scan(1)
    async def handle_monitor(self):
        response, image_bytes = await self.connection.get_bytes(
            f"monitor/api/{self._api_version}/images/next"
        )
        if response.status != 200:
            return
        frame = np.array(Image.open(BytesIO(image_bytes)))
        frame = np.clip(frame, self.image_min.get(), self.image_max.get())
        await self.image.update(frame)
