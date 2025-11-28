import json
from pathlib import Path

import pytest
from fastcs_odin.util import create_odin_parameters
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

    assert len(eiger_fan.attributes) == 28

    # Check `0/status/` removed
    assert eiger_fan.timestamp.path == []  # type: ignore
