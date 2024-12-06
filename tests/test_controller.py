import asyncio
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_controller import (
    EigerController,
    EigerDetectorController,
    EigerHandler,
)

_lock = asyncio.Lock()


@pytest.mark.asyncio
async def test_eiger_controller_creates_subcontrollers(mocker: MockerFixture):
    eiger_controller = EigerController("127.0.0.1", 80)
    connection = mocker.patch.object(eiger_controller, "connection")
    connection.get = mocker.AsyncMock()
    connection.put = mocker.AsyncMock()
    await eiger_controller.initialise()
    assert list(eiger_controller.get_sub_controllers().keys()) == [
        "Detector",
        "Stream",
        "Monitor",
    ]
    connection.get.assert_any_call("detector/api/1.8.0/status/state")
    connection.get.assert_any_call("detector/api/1.8.0/status/keys")
    connection.get.assert_any_call("detector/api/1.8.0/config/keys")
    connection.get.assert_any_call("monitor/api/1.8.0/status/keys")
    connection.get.assert_any_call("monitor/api/1.8.0/config/keys")
    connection.get.assert_any_call("stream/api/1.8.0/status/keys")
    connection.get.assert_any_call("stream/api/1.8.0/config/keys")


@pytest.mark.asyncio
async def test_eiger_handler_update_updates_value(mocker: MockerFixture):
    dummy_uri = "subsystem/api/1.8.0/dummy_mode/dummy_uri"
    updater = EigerHandler(dummy_uri)
    controller = mocker.AsyncMock()
    attr = mocker.Mock()

    controller.connection.get.return_value = {"value": 5}

    await updater.update(controller, attr)
    attr.set.assert_called_once_with(5)


@pytest.mark.asyncio
async def test_eiger_handler_put(mocker: MockerFixture):
    dummy_uri = "subsystem/api/1.8.0/dummy_mode/dummy_uri"
    controller = mocker.AsyncMock()
    await EigerHandler(dummy_uri).put(controller, mocker.Mock(), 0.1)
    controller.connection.put.assert_awaited_once_with(dummy_uri, 0.1)
    controller.queue_update.assert_awaited_once_with(
        controller.connection.put.return_value
    )

    # if controller.connection.put returns [],
    # still queue_update for the handled uri
    controller.connection.put.return_value = []
    no_updated_params_uri = "susbsystem/api/1.8.0/dummy_mode/no_updated_params"
    await EigerHandler(no_updated_params_uri).put(controller, mocker.Mock(), 0.1)
    controller.connection.put.assert_awaited_with(no_updated_params_uri, 0.1)
    controller.queue_update.assert_awaited_with(["no_updated_params"])


@pytest.mark.asyncio
async def test_stale_parameter_propagates_to_top_controller(mocker: MockerFixture):
    eiger_controller = EigerController("127.0.0.1", 80)
    connection = mocker.patch.object(eiger_controller, "connection")
    connection.get = mock.AsyncMock()

    await eiger_controller.initialise()

    detector_controller = eiger_controller.get_sub_controllers()["Detector"]
    assert isinstance(detector_controller, EigerDetectorController)
    # queueing update sets subcontroller to stale
    assert detector_controller.stale_parameters.get() is False
    await detector_controller.queue_update(["dummy_attribute"])
    assert detector_controller.stale_parameters.get() is True

    # top controller not stale until update called
    assert eiger_controller.stale_parameters.get() is False
    await eiger_controller.update()
    assert eiger_controller.stale_parameters.get() is True
    assert detector_controller.stale_parameters.get() is True

    # on next update, queued updates are handled and stale is cleared
    await eiger_controller.update()
    assert not detector_controller.stale_parameters.get()
    assert eiger_controller.stale_parameters.get()

    # top controller needs to update another final time so that the
    # detector controller stale  attribute returning to False propagates to top
    await eiger_controller.update()
    assert not eiger_controller.stale_parameters.get()
