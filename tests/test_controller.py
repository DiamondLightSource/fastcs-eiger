import asyncio

import pytest
from fastcs.attributes import Attribute
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_controller import (
    IGNORED_KEYS,
    MISSING_KEYS,
    EigerController,
    EigerDetectorController,
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
