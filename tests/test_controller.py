import pytest
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_controller import EigerController


@pytest.mark.asyncio
async def test_initialise(mocker: MockerFixture):
    controller = EigerController("127.0.0.1", 80)

    connection = mocker.patch.object(controller, "connection")
    connection.get = mocker.AsyncMock()
    connection.get.return_value = {"value": "idle"}
    initialize = mocker.patch.object(controller, "initialize")
    introspect = mocker.patch.object(controller, "_introspect_detector")
    create_attributes = mocker.patch.object(controller, "_create_attributes")
    attr = mocker.MagicMock()
    create_attributes.return_value = {"attr_name": attr}

    await controller.initialise()

    connection.get.assert_called_once_with("detector/api/1.8.0/status/state")
    initialize.assert_not_called()
    introspect.assert_awaited_once_with()
    create_attributes.assert_called_once_with(introspect.return_value)
    assert controller.attr_name == attr, "Attribute not added to controller"


@pytest.mark.asyncio
async def test_initialise_state_na(mocker: MockerFixture):
    controller = EigerController("127.0.0.1", 80)

    connection = mocker.patch.object(controller, "connection")
    connection.get = mocker.AsyncMock()
    connection.get.return_value = {"value": "na"}
    initialize = mocker.patch.object(controller, "initialize")
    introspect = mocker.patch.object(controller, "_introspect_detector")
    create_attributes = mocker.patch.object(controller, "_create_attributes")

    await controller.initialise()

    connection.get.assert_called_once_with("detector/api/1.8.0/status/state")
    initialize.assert_awaited_once_with()
    introspect.assert_awaited_once_with()
    create_attributes.assert_called_once_with(introspect.return_value)
