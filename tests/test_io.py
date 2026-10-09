import pytest
from fastcs.attributes import AttrRW
from fastcs.datatypes import Bool
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_parameter import EigerParameterRef, EigerParameterResponse
from fastcs_eiger.io import EigerAttributeIO


@pytest.fixture
def connection_mock(mocker: MockerFixture):
    return mocker.AsyncMock()


@pytest.fixture
def mode_attribute() -> AttrRW[bool]:
    ref = EigerParameterRef(
        key="mode",
        subsystem="monitor",
        api_version="1.6.0",
        mode="config",
        response=EigerParameterResponse(
            access_mode="rw",
            value="enabled",
            value_type="string",
            allowed_values=["enabled", "disabled"],
        ),
    )
    # Subcontrollers make a Bool attr if allowed values are ["enabled", "disabled"]
    return AttrRW(Bool(), io_ref=ref)


@pytest.fixture
def io(connection_mock, mocker: MockerFixture) -> EigerAttributeIO:
    return EigerAttributeIO(connection_mock, mocker.AsyncMock(), mocker.AsyncMock())


@pytest.mark.asyncio
async def test_update(io, connection_mock, mocker):
    attr = mocker.AsyncMock()

    connection_mock.get.return_value = {"value": 1}
    await io.update(attr)

    attr.update.assert_called_once_with(1)

    connection_mock.get.return_value = {"value": None}
    await io.update(attr)

    attr.update.assert_called_with(attr.datatype.initial_value)


@pytest.mark.asyncio
async def test_eiger_io_send_converts_bool_to_enabled_disabled(
    io: EigerAttributeIO, connection_mock, mode_attribute
):
    await io.send(mode_attribute, True)
    connection_mock.put.assert_called_once_with(
        "monitor/api/1.6.0/config/mode", "enabled"
    )

    await io.send(mode_attribute, False)
    connection_mock.put.assert_called_with("monitor/api/1.6.0/config/mode", "disabled")


@pytest.mark.asyncio
async def test_eiger_io_update_converts_enabled_disabled_to_bool(
    io: EigerAttributeIO, connection_mock, mode_attribute
):
    connection_mock.get.side_effect = [{"value": "enabled"}, {"value": "disabled"}]

    await io.update(mode_attribute)
    assert mode_attribute.get() is True

    await io.update(mode_attribute)
    assert mode_attribute.get() is False
