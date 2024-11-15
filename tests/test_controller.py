import asyncio
from unittest import mock

import pytest
from fastcs.attributes import Attribute
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_controller import (
    IGNORED_KEYS,
    MISSING_KEYS,
    EigerConfigHandler,
    EigerController,
    EigerDetectorController,
    EigerHandler,
    EigerMonitorController,
    EigerStreamController,
)

_lock = asyncio.Lock()


@pytest.mark.asyncio
async def test_detector_controller(
    mock_connection, detector_config_keys, detector_status_keys
):
    detector_controller = EigerDetectorController(mock_connection, _lock)
    parameters = await detector_controller._introspect_detector_subsystem()
    assert all(parameter.key not in IGNORED_KEYS for parameter in parameters)
    for parameter in parameters:
        assert parameter.key not in IGNORED_KEYS
        if parameter.mode == "config":
            assert (
                parameter.key in detector_config_keys
                or parameter.key in MISSING_KEYS["detector"]["config"]
            )
        elif parameter.mode == "status":
            assert (
                parameter.key in detector_status_keys
                or parameter.key in MISSING_KEYS["detector"]["status"]
            )

    # test queue_update side effect
    assert not detector_controller.stale_parameters.get()
    await detector_controller.queue_update(["chi_start"])
    assert detector_controller._parameter_updates == {"chi_start"}
    assert detector_controller.stale_parameters.get()


@pytest.mark.asyncio
async def test_monitor_controller_initialises(mock_connection):
    subsystem_controller = EigerMonitorController(mock_connection, _lock)
    await subsystem_controller.initialise()


@pytest.mark.asyncio
async def test_stream_controller_initialises(mock_connection):
    subsystem_controller = EigerStreamController(mock_connection, _lock)
    await subsystem_controller.initialise()


@pytest.mark.asyncio
async def test_detector_subsystem_controller(mock_connection):
    subsystem_controller = EigerDetectorController(mock_connection, _lock)
    await subsystem_controller.initialise()

    for attr_name in dir(subsystem_controller):
        attr = getattr(subsystem_controller, attr_name)
        if isinstance(attr, Attribute) and "threshold" in attr_name:
            if attr_name == "threshold_energy":
                continue
            assert "Threshold" in attr.group


@pytest.mark.asyncio
async def test_eiger_controller_initialises(mocker: MockerFixture, mock_connection):
    eiger_controller = EigerController("127.0.0.1", 80)
    connection = mocker.patch.object(eiger_controller, "connection")
    connection.get = mock_connection.get
    await eiger_controller.initialise()
    assert list(eiger_controller.get_sub_controllers().keys()) == [
        "Detector",
        "Stream",
        "Monitor",
    ]
    connection.get.assert_any_call("detector/api/1.8.0/status/state")
    connection.get.assert_any_call("stream/api/1.8.0/status/state")
    connection.get.assert_any_call("monitor/api/1.8.0/status/state")


@pytest.mark.asyncio
async def test_eiger_handler_after_put(mock_connection):
    subsystem_controller = EigerDetectorController(mock_connection, _lock)
    await subsystem_controller.initialise()
    attr = subsystem_controller.humidity
    handler = attr.sender

    assert type(handler) is EigerHandler
    assert not subsystem_controller.stale_parameters.get()
    await handler.put(subsystem_controller, attr, 0.1)
    # eiger API does not return a list of updated parameters when we set status keys
    # so _parameter_updates set to default case where we only update the key we changed
    assert subsystem_controller._parameter_updates == {"humidity"}
    # humidity is really read-only but given here for demonstration
    assert subsystem_controller.stale_parameters.get()

    # parameters with EigerHandler handlers do not get updated when
    # controller update is called

    subsystem_controller.humidity.updater.update = mock.AsyncMock()

    await subsystem_controller.update()
    assert subsystem_controller.stale_parameters.get()
    subsystem_controller.humidity.updater.update.assert_not_called()

    await subsystem_controller.update()
    # stale does not get set False unless there are no stale parameters at start of
    # update call
    assert not subsystem_controller.stale_parameters.get()
    assert not subsystem_controller._parameter_updates


@pytest.mark.asyncio
async def test_eiger_handler_update_updates_value(mock_connection):
    subsystem_controller = EigerDetectorController(mock_connection, _lock)
    await subsystem_controller.initialise()

    async def _get_1_as_value(*args, **kwargs):
        return {"access_mode": "r", "value": 1, "value_type": "int"}

    assert type(subsystem_controller.state.updater) is EigerHandler
    assert subsystem_controller.state.get() == 0

    mock_connection.get = _get_1_as_value
    # show that value changes after update is awaited
    await subsystem_controller.state.updater.update(
        subsystem_controller, subsystem_controller.state
    )
    assert subsystem_controller.state.get() == 1


@pytest.mark.asyncio
async def test_EigerConfigHandler(mock_connection):
    subsystem_controller = EigerDetectorController(mock_connection, _lock)
    await subsystem_controller.initialise()
    attr = subsystem_controller.threshold_1_energy
    handler = attr.sender
    assert isinstance(handler, EigerConfigHandler)
    assert not subsystem_controller.stale_parameters.get()
    await handler.put(subsystem_controller, attr, 100.0)
    expected_changed_params = [
        "flatfield",
        "threshold/1/energy",
        "threshold/1/flatfield",
        "threshold/2/flatfield",
        "threshold_energy",
    ]
    assert subsystem_controller._parameter_updates == set(expected_changed_params)
    assert subsystem_controller.stale_parameters.get()

    # flatfields are ignored keys
    subsystem_controller.threshold_energy.updater.config_update = mock.AsyncMock()

    await subsystem_controller.update()
    assert subsystem_controller.stale_parameters.get()
    subsystem_controller.threshold_energy.updater.config_update.assert_called_once_with(
        subsystem_controller, subsystem_controller.threshold_energy
    )

    await subsystem_controller.update()
    # stale does not get set False unless there are no stale parameters at start of
    # update call
    assert not subsystem_controller.stale_parameters.get()
    assert not subsystem_controller._parameter_updates


@pytest.mark.asyncio
async def test_stale_parameter_propagates_to_top_controller(mock_connection):
    top_controller = EigerController("127.0.0.1", 80)
    top_controller.connection = mock_connection
    await top_controller.initialise()
    detector_controller = top_controller.get_sub_controllers()["Detector"]
    attr = detector_controller.threshold_energy

    assert not detector_controller.stale_parameters.get()
    assert not top_controller.stale_parameters.get()

    await attr.sender.put(detector_controller, attr, 100.0)
    assert detector_controller.stale_parameters.get()
    # top controller not stale until update called
    assert not top_controller.stale_parameters.get()
    await top_controller.update()
    assert top_controller.stale_parameters.get()

    # need to update again to make detector controller update its
    # stale parameter attribute
    await top_controller.update()
    assert not detector_controller.stale_parameters.get()
    assert top_controller.stale_parameters.get()

    # top controller needs to update another final time so that the
    # detector controller stale  attribute returning to False propagates to top
    await top_controller.update()
    assert not top_controller.stale_parameters.get()
