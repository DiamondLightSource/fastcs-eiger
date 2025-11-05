from pathlib import Path
from typing import Optional

import typer
from fastcs.launch import FastCS
from fastcs.transport.epics.ca.options import (
    EpicsGUIOptions,
    EpicsIOCOptions,
)
from fastcs.transport.epics.ca.transport import EpicsCATransport

from fastcs_eiger import __version__
from fastcs_eiger.eiger_controller import EigerController

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


EigerIp = typer.Option("127.0.0.1", help="IP address of Eiger detector")
EigerPort = typer.Option(8081, help="Port of Eiger HTTP server")

OPI_PATH = Path("/epics/opi")


@app.command()
def ioc(
    pv_prefix: str = typer.Argument(),
    ip: str = EigerIp,
    port: int = EigerPort,
):
    ui_path = OPI_PATH if OPI_PATH.is_dir() else Path.cwd()

    controller = EigerController(ip, port)

    options = EpicsCATransport(
        ca_ioc=EpicsIOCOptions(pv_prefix=pv_prefix),
        gui=EpicsGUIOptions(
            output_path=ui_path / "eiger.bob", title=f"Eiger - {pv_prefix}"
        ),
    )
    launcher = FastCS(controller, [options])
    launcher.run()


# test with: python -m fastcs_eiger
if __name__ == "__main__":
    app()
