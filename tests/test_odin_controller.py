import pytest
from fastcs.connections import IPConnectionSettings
from fastcs_odin.meta_writer import MetaWriterAdapterController
from fastcs_odin.util import OdinParameter, OdinParameterMetadata
from pytest_mock import MockerFixture

from fastcs_eiger.odin.eiger_fan import EigerFanAdapterController
from fastcs_eiger.odin.odin_controller import OdinController


@pytest.mark.asyncio
async def test_create_adapter_controller(mocker: MockerFixture):
    controller = OdinController(IPConnectionSettings("", 0))
    controller.connection = mocker.AsyncMock()
    parameters = [
        OdinParameter(
            ["0"], metadata=OdinParameterMetadata(value=0, type="int", writeable=False)
        )
    ]

    ctrl = controller._create_adapter_controller(
        controller.connection, parameters, "ef", "EigerFanAdapter"
    )
    assert isinstance(ctrl, EigerFanAdapterController)

    ctrl = controller._create_adapter_controller(
        controller.connection, parameters, "mw", "MetaListenerAdapter"
    )
    assert isinstance(ctrl, MetaWriterAdapterController)
