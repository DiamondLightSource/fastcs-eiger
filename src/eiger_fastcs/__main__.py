from pathlib import Path
from typing import Optional

import typer
from fastcs.backends.asyncio_backend import AsyncioBackend
from fastcs.backends.epics.backend import EpicsBackend
from fastcs.backends.epics.gui import EpicsGUIOptions
from fastcs.mapping import Mapping

from eiger_fastcs import __version__
from eiger_fastcs.eiger_controller import EigerController

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


EigerUrl = typer.Option("127.0.0.1", help="URL of Eiger detector")
EigerPort = typer.Option(8081, help="Port of Eiger HTTP server")


@app.command()
def ioc(pv_prefix: str = typer.Argument(), url: str = EigerUrl, port: int = EigerPort):
    mapping = get_controller_mapping(url, port)

    backend = EpicsBackend(mapping, pv_prefix)
    backend.create_gui(
        EpicsGUIOptions(
            output_path=Path.cwd() / "eiger.bob", title=f"Eiger - {pv_prefix}"
        )
    )
    backend.get_ioc().run()


@app.command()
def asyncio(url: str = EigerUrl, port: int = EigerPort):
    mapping = get_controller_mapping(url, port)

    backend = AsyncioBackend(mapping)
    backend.run_interactive_session()


def get_controller_mapping(url: str, port: int) -> Mapping:
    controller = EigerController(url, port)

    return Mapping(controller)


# test with: python -m eiger_fastcs
if __name__ == "__main__":
    app()
