import asyncio
from pathlib import Path

from fastcs.attributes import AttrRW
from fastcs.connections import IPConnectionSettings
from fastcs.datatypes import Bool
from fastcs.methods import command

from fastcs_eiger.controllers.eiger_controller import EigerController
from fastcs_eiger.controllers.odin.generate_vds import create_interleave_vds
from fastcs_eiger.controllers.odin.odin_controller import OdinController


class EigerOdinController(EigerController):
    """Eiger controller with Odin sub controller"""

    enable_vds_creation = AttrRW(Bool())

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

        if self.enable_vds_creation.get():
            create_interleave_vds(
                path=Path(self.OD.file_path.get()),
                prefix=self.OD.file_prefix.get(),
                datasets=["data"],  # NEED TO GET THIS FROM SOMEWHERE
                frame_count=self.OD.FP.frames.get(),
                frames_per_block=self.OD.block_size.get(),
                blocks_per_file=self.OD.FP.process_blocks_per_file.get(),
                frame_shape=(
                    self.OD.FP.data_dims_1.get(),
                    self.OD.FP.data_dims_0.get(),
                ),
                dtype=self.OD.FP.data_datatype.get(),
            )
