import asyncio
from typing import Any

import aioca
import typer

CA_TIMEOUT = 3


def main(
    prefix: str = "EIGER",
    file_path: str = "/data",
    file_name: str = "test",
    frames: int = 10,
    exposure_time: float = 1,
):
    asyncio.run(run_acquisition(prefix, file_path, file_name, frames, exposure_time))


async def run_acquisition(
    prefix: str,
    file_path: str,
    file_name: str,
    frames: int,
    exposure_time: float,
):
    eiger_prefix = prefix
    odin_prefix = f"{prefix}:OD"

    await tidy(eiger_prefix, odin_prefix)

    print("Configuring")
    await asyncio.gather(
        caput(f"{odin_prefix}:BlockSize", 1),
        caput_str(f"{odin_prefix}:FilePath", file_path),
        caput_str(f"{odin_prefix}:AcquisitionId", file_name),
        caput(f"{odin_prefix}:FP:Frames", frames),
        caput(f"{eiger_prefix}:Detector:Nimages", frames),
        caput(f"{eiger_prefix}:Detector:Ntrigger", 1),
        caput(f"{eiger_prefix}:Detector:FrameTime", exposure_time),
        # caput(f"{eiger_prefix}:Detector:TriggerMode", "ints"),  # for real detector
        caput_str(f"{eiger_prefix}:Detector:TriggerMode", "ints"),  # for tickit sim
    )

    print("Arming")
    await caput(f"{eiger_prefix}:ArmWhenReady", True)

    print("Starting writing")
    await caput(f"{eiger_prefix}:StartWriting", True)

    print("Triggering")
    await caput(f"{eiger_prefix}:Detector:Trigger", True, wait=False)

    print("Waiting")
    await pv_equals(
        f"{odin_prefix}:Writing",
        0,
        timeout=exposure_time * frames * 5,  # tickit sim is much slower than requested
    )

    print("Finished")
    await tidy(eiger_prefix, odin_prefix)


async def tidy(eiger_prefix: str, odin_prefix: str):
    await caput(f"{odin_prefix}:FP:StopWriting", True)
    await caput(f"{eiger_prefix}:Detector:Abort", True)


async def caput_str(pv: str, value: Any, **kwargs):
    await caput(pv, value, datatype=aioca.DBR_CHAR_STR, **kwargs)


async def caput(
    pv: str,
    value: Any,
    wait: bool = True,
    timeout: aioca._catools.Timeout = CA_TIMEOUT,
    **kwargs,
):
    print(f"Setting {pv} to {value}")
    await aioca.caput(pv, value, wait=wait, timeout=timeout, **kwargs)


async def pv_equals(pv: str, value: Any, timeout: float = 10):
    while timeout > 0:
        current = await aioca.caget(pv, timeout=1)
        if current == value:
            return

        print(f"{pv}: {value} != {current}")
        await asyncio.sleep(1)
        timeout -= 1

    print(f"Timed out waiting for {pv} to equal {value}")


if __name__ == "__main__":
    typer.run(main)
