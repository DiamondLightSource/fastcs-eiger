import json
from pathlib import Path

import pytest
from fastcs_odin.io.parameter_attribute_io import ParameterTreeAttributeIO
from fastcs_odin.io.status_summary_attribute_io import StatusSummaryAttributeIO
from fastcs_odin.util import (
    OdinParameter,
    OdinParameterMetadata,
    create_odin_parameters,
)
from pytest_mock import MockerFixture

from fastcs_eiger.odin.eiger_fan import EigerFanAdapterController

HERE = Path(__file__).parent


@pytest.mark.asyncio
async def test_ef_initialise(mocker: MockerFixture):
    with (HERE / "input/ef_response.json").open() as f:
        response = json.loads(f.read())

    mock_connection = mocker.MagicMock()

    parameters = create_odin_parameters(response)
    eiger_fan = EigerFanAdapterController(mock_connection, parameters, "prefix", [])
    await eiger_fan.initialise()

    assert len(eiger_fan.attributes) == 29

    # Check `0/status/` removed
    assert eiger_fan.timestamp.path == []  # type: ignore


@pytest.mark.asyncio
async def test_ef_ready(mocker: MockerFixture):
    mock_connection = mocker.MagicMock()
    state_parameter = OdinParameter(
        ["state"], metadata=OdinParameterMetadata(value=0, writeable=False, type="str")
    )
    eiger_fan = EigerFanAdapterController(
        mock_connection,
        [state_parameter],
        "prefix",
        [StatusSummaryAttributeIO(), ParameterTreeAttributeIO(mock_connection)],
    )
    await eiger_fan.initialise()
    eiger_fan.post_initialise()

    ready_update = eiger_fan.ready.bind_update_callback()

    assert not eiger_fan.ready.get()
    await eiger_fan.state.update("DSTR_HEADER")
    await ready_update()
    assert eiger_fan.ready.get()
