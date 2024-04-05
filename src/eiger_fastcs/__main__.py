from argparse import ArgumentParser

from fastcs.backends.asyncio_backend import AsyncioBackend
from fastcs.backends.epics.backend import EpicsBackend
from fastcs.mapping import Mapping

from eiger_fastcs import __version__
from eiger_fastcs.eiger_controller import EigerController

__all__ = ["main"]


def get_controller() -> EigerController:
    return EigerController("127.0.0.1", 8081)
    # return EigerController("i03-eiger01", 80)


def create_gui(controller) -> None:
    m = Mapping(controller)
    backend = EpicsBackend(m)
    backend.create_gui()


def test_ioc(controller) -> None:
    m = Mapping(controller)
    backend = EpicsBackend(m)
    ioc = backend.get_ioc()
    ioc.run()


def test_asyncio_backend(controller) -> None:
    m = Mapping(controller)
    backend = AsyncioBackend(m)
    backend.run_interactive_session()


def main(args=None):
    parser = ArgumentParser()
    parser.add_argument("-v", "--version", action="version", version=__version__)
    args = parser.parse_args(args)

    controller = get_controller()
    create_gui(controller)
    test_ioc(controller)


# test with: python -m eiger_fastcs
if __name__ == "__main__":
    main()
