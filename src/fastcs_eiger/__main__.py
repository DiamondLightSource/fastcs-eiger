from pathlib import Path
from typing import Optional

import typer
from fastcs.connections import IPConnectionSettings
from fastcs.launch import FastCS
from fastcs.logging import LogLevel, configure_logging
from fastcs.transports.epics import EpicsGUIOptions, EpicsIOCOptions
from fastcs.transports.epics.ca.transport import EpicsCATransport
from fastcs.transports.epics.pva.transport import EpicsPVATransport

from fastcs_eiger import __version__
from fastcs_eiger.controllers.eiger_controller import EigerController
from fastcs_eiger.controllers.odin.eiger_odin_controller import EigerOdinController
from fastcs_eiger.eiger_parameter import EigerAPIVersion

__all__ = ["main"]


app = typer.Typer()


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    # TODO: typer does not support `bool | None` yet
    # https://github.com/tiangolo/typer/issues/533
    version: Optional[bool] = typer.Option(  # noqa
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Print the version and exit",
    ),
):
    pass


OPI_PATH = Path("/epics/opi")


@app.command()
def ioc(
    pv_prefix: str = typer.Argument(),
    ip: str = typer.Option("127.0.0.1", help="IP address of Eiger detector"),
    port: int = typer.Option(8081, help="Port of Eiger HTTP server"),
    api_version: EigerAPIVersion = typer.Option("1.8.0", help="Version of Eiger API"),  # noqa: B008
    odin_ip: str | None = typer.Option(None, help="IP address of odin control server"),
    odin_port: int = typer.Option(8888, help="Port of odin control server"),
    log_level: LogLevel = LogLevel.TRACE,
):
    ui_path = OPI_PATH if OPI_PATH.is_dir() else Path.cwd() / "opi"

    configure_logging(log_level)

    if odin_ip is None:
        controller = EigerController(
            connection_settings=IPConnectionSettings(ip=ip, port=port),
            api_version=api_version,
        )
    else:
        controller = EigerOdinController(
            detector_connection_settings=IPConnectionSettings(ip=ip, port=port),
            odin_connection_settings=IPConnectionSettings(ip=odin_ip, port=odin_port),
            api_version=api_version,
        )

    transports = [
        EpicsPVATransport(
            epicspva=EpicsIOCOptions(pv_prefix=pv_prefix),
            gui=EpicsGUIOptions(
                output_path=ui_path / "eiger.bob", title=f"Eiger - {pv_prefix}"
            ),
        ),
        EpicsCATransport(
            epicsca=EpicsIOCOptions(pv_prefix=pv_prefix),
        ),
    ]
    launcher = FastCS(controller, transports)
    launcher.run()


# test with: python -m fastcs_eiger
if __name__ == "__main__":
    app()
