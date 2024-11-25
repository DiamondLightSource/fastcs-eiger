import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
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

Getter = Callable[[str], Awaitable[dict[str, Any] | list[str]]]
Putter = Callable[[str, Any], Awaitable[list[str]]]


@pytest.fixture
def dummy_getter(keys_mapping: dict[str, list[str]]) -> Getter:
    # if not in mapping, get dummy parameter dict
    async def _getter(uri: str):
        return keys_mapping.get(
            uri, {"access_mode": "rw", "value": 0.0, "value_type": "float"}
        )

    return _getter


@pytest.fixture
def dummy_putter(put_response_mapping: dict[str, list[str]]) -> Putter:
    async def _putter(uri: str, _: Any):
        key = uri.split("/", 4)[-1]
        # return [key] if not in mapping
        return put_response_mapping.get(key, [key])

    return _putter


@pytest.mark.asyncio
async def test_detector_controller(
    dummy_getter: Getter,
    detector_config_keys: list[str],
    detector_status_keys: list[str],
):
    connection = mock.Mock()
    connection.get = dummy_getter

    detector_controller = EigerDetectorController(connection, _lock)
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
async def test_monitor_controller_initialises(dummy_getter: Getter):
    connection = mock.Mock()
    connection.get = dummy_getter
    subsystem_controller = EigerMonitorController(connection, _lock)
    await subsystem_controller.initialise()


@pytest.mark.asyncio
async def test_stream_controller_initialises(dummy_getter: Getter):
    connection = mock.Mock()
    connection.get = dummy_getter
    subsystem_controller = EigerStreamController(connection, _lock)
    await subsystem_controller.initialise()


@pytest.mark.asyncio
async def test_detector_subsystem_controller(dummy_getter: Getter):
    connection = mock.Mock()
    connection.get = dummy_getter
    subsystem_controller = EigerDetectorController(connection, _lock)
    await subsystem_controller.initialise()

    for attr_name in dir(subsystem_controller):
        attr = getattr(subsystem_controller, attr_name)
        if isinstance(attr, Attribute) and "threshold" in attr_name:
            if attr_name == "threshold_energy":
                continue
            assert attr.group and "Threshold" in attr.group


@pytest.mark.asyncio
async def test_eiger_controller_initialises(
    mocker: MockerFixture, dummy_getter: Getter
):
    eiger_controller = EigerController("127.0.0.1", 80)
    connection = mocker.patch.object(eiger_controller, "connection")
    connection.get.side_effect = dummy_getter

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
async def test_eiger_handler_update_updates_value(keys_mapping: dict[str, list[str]]):
    connection = mock.Mock()

    async def _get(uri: str) -> dict[str, Any] | list[str]:
        if "state" in uri:  # get 1 as value for state
            return {"access_mode": "r", "value": 1, "value_type": "int"}
        # if not in mapping, get dummy parameter dict
        return keys_mapping.get(
            uri, {"access_mode": "rw", "value": 0.0, "value_type": "float"}
        )

    connection.get = _get
    subsystem_controller = EigerDetectorController(connection, _lock)
    await subsystem_controller.initialise()

    assert type(subsystem_controller.state.updater) is EigerHandler
    assert subsystem_controller.state.get() == 0

    # show that value changes after update is awaited
    await subsystem_controller.state.updater.update(
        subsystem_controller, subsystem_controller.state
    )
    assert subsystem_controller.state.get() == 1


@pytest.mark.asyncio
async def test_eiger_config_handler_put(dummy_getter: Getter, dummy_putter: Putter):
    connection = mock.Mock()
    connection.get.side_effect = dummy_getter
    connection.put.side_effect = dummy_putter
    subsystem_controller = EigerDetectorController(connection, _lock)
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
async def test_stale_parameter_propagates_to_top_controller(
    mocker: MockerFixture,
    dummy_getter: Getter,
    dummy_putter: Putter,
):
    eiger_controller = EigerController("127.0.0.1", 80)
    connection = mocker.patch.object(eiger_controller, "connection")
    connection.get.side_effect = dummy_getter
    connection.put.side_effect = dummy_putter

    await eiger_controller.initialise()

    detector_controller = eiger_controller.get_sub_controllers()["Detector"]
    attr = detector_controller.threshold_energy

    assert not detector_controller.stale_parameters.get()
    assert not eiger_controller.stale_parameters.get()

    await attr.sender.put(detector_controller, attr, 100.0)
    assert detector_controller.stale_parameters.get()
    # top controller not stale until update called
    assert not eiger_controller.stale_parameters.get()
    await eiger_controller.update()
    assert eiger_controller.stale_parameters.get()

    # need to update again to make detector controller update its
    # stale parameter attribute
    await eiger_controller.update()
    assert not detector_controller.stale_parameters.get()
    assert eiger_controller.stale_parameters.get()

    # top controller needs to update another final time so that the
    # detector controller stale  attribute returning to False propagates to top
    await eiger_controller.update()
    assert not eiger_controller.stale_parameters.get()
