from pathlib import Path
from typing import Optional

import typer
from fastcs.backends.asyncio_backend import AsyncioBackend
from fastcs.backends.epics.backend import EpicsBackend
from fastcs.backends.epics.gui import EpicsGUIOptions

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

    backend = EpicsBackend(controller, pv_prefix)
    backend.create_gui(
        EpicsGUIOptions(output_path=ui_path / "eiger.bob", title=f"Eiger - {pv_prefix}")
    )
    backend.run()


@app.command()
def asyncio(ip: str = EigerIp, port: int = EigerPort):
    controller = EigerController(ip, port)

    backend = AsyncioBackend(controller)
    backend.run_interactive_session()


# test with: python -m fastcs_eiger
if __name__ == "__main__":
    app()
