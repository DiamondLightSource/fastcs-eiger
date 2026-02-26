from io import BytesIO

import numpy as np
from fastcs.methods import scan
from PIL import Image

from fastcs_eiger.controllers.eiger_subsystem_controller import EigerSubsystemController


class EigerMonitorController(EigerSubsystemController):
    _subsystem = "monitor"

    @scan(1)
    async def handle_monitor(self):
        """Poll monitor images to display."""
        response, image_bytes = await self.connection.get_bytes(
            f"monitor/api/{self._api_version}/images/next"
        )
        if response.status != 200:
            return
        else:
            image = Image.open(BytesIO(image_bytes))

            # TODO: Populate waveform PV to display as image, once supported in PVI
            print(np.array(image))
