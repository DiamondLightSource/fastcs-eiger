import pytest
from pytest_mock import MockerFixture

from fastcs_eiger.io import EigerAttributeIO


@pytest.mark.asyncio
async def test_update(mocker: MockerFixture):
    connection_mock = mocker.AsyncMock()
    io = EigerAttributeIO(connection_mock, mocker.MagicMock(), mocker.MagicMock())
    attr = mocker.AsyncMock()

    connection_mock.get.return_value = {"value": 1}
    await io.update(attr)

    attr.update.assert_called_once_with(1)

    connection_mock.get.return_value = {"value": None}
    await io.update(attr)

    attr.update.assert_called_with(attr.datatype.initial_value)
