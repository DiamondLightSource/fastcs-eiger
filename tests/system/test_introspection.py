import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastcs.attributes import Attribute, AttrR, AttrRW
from fastcs.datatypes import Float
from pydantic import ValidationError
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_controller import (
    IGNORED_KEYS,
    MISSING_KEYS,
    EigerConfigHandler,
    EigerController,
    EigerDetectorController,
    EigerMonitorController,
    EigerParameter,
    EigerParameterResponse,
    EigerStreamController,
    EigerSubsystemController,
)

HERE = Path(__file__).parent

EIGER_PARAMETER_VALID_VALUES = EigerParameterResponse.__annotations__[
    "value_type"
].__args__


def _serialise_parameter(parameter: EigerParameter) -> dict:
    return {
        "subsystem": parameter.subsystem,
        "mode": parameter.mode,
        "key": parameter.key,
        "response": {
            k: v
            for k, v in parameter.response.model_dump(exclude_none=True).items()
            if k not in ("max", "min", "unit", "value")
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sim_eiger_controller", [str(HERE / "eiger.yaml")], indirect=True
)
async def test_attribute_creation(sim_eiger_controller: EigerController):
    controller = sim_eiger_controller
    await controller.initialise()
    serialised_parameters: dict[str, dict[str, Any]] = {}
    subsystem_parameters = {}
    for subcontroller in controller.get_subsystem_controllers():
        serialised_parameters[subcontroller._subsystem] = {}
        subsystem_parameters[
            subcontroller._subsystem
        ] = await subcontroller._introspect_detector_subsystem()
        for param in subsystem_parameters[subcontroller._subsystem]:
            serialised_parameters[subcontroller._subsystem][param.key] = (
                _serialise_parameter(param)
            )

    expected_file = HERE / "parameters.json"
    if os.environ.get("REGENERATE_TEST_OUTPUT", None):
        expected_file.write_text(json.dumps(serialised_parameters, indent=4))

    expected_parameters = json.loads(expected_file.read_text())

    assert serialised_parameters == expected_parameters, "Detector API does not match"

    detector_attributes = EigerDetectorController._create_attributes(
        subsystem_parameters["detector"]
    )
    assert len(detector_attributes) == 76
    monitor_attributes = EigerMonitorController._create_attributes(
        subsystem_parameters["monitor"]
    )
    assert len(monitor_attributes) == 7
    stream_attributes = EigerStreamController._create_attributes(
        subsystem_parameters["stream"]
    )
    assert len(stream_attributes) == 8

    assert isinstance(detector_attributes["humidity"], AttrR)
    assert isinstance(detector_attributes["humidity"].datatype, Float)
    assert detector_attributes["humidity"]._group == "DetectorStatus"
    assert detector_attributes["threshold_2_energy"]._group == "Threshold2"
    assert (
        detector_attributes["threshold_difference_lower_threshold"]._group
        == "ThresholdDifference"
    )

    await controller.connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sim_eiger_controller", [str(HERE / "eiger.yaml")], indirect=True
)
async def test_controller_groups_and_parameters(sim_eiger_controller: EigerController):
    controller = sim_eiger_controller
    await controller.initialise()

    for subsystem in MISSING_KEYS:
        subcontroller = controller.get_sub_controllers()[subsystem.title()]
        assert isinstance(subcontroller, EigerSubsystemController)
        parameters = await subcontroller._introspect_detector_subsystem()
        if subsystem == "detector":
            # ignored keys should not get added to the controller
            assert all(param.key not in IGNORED_KEYS for param in parameters)

            # threshold parameters should belong to own group
            for attr_name in dir(subcontroller):
                attr = getattr(subcontroller, attr_name)
                if isinstance(attr, Attribute) and "threshold" in attr_name:
                    if attr_name == "threshold_energy":
                        continue
                    assert attr.group and "Threshold" in attr.group

        for keys in MISSING_KEYS[subsystem].values():  # loop over status, config keys
            for key in keys:
                assert any(param.key == key for param in parameters)

    await controller.connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sim_eiger_controller", [str(HERE / "eiger.yaml")], indirect=True
)
async def test_threshold_mode_api_consistency_handled(
    sim_eiger_controller: EigerController, mocker: MockerFixture
):
    controller = sim_eiger_controller
    await controller.initialise()
    detector_controller = controller.get_sub_controllers()["Detector"]
    assert isinstance(detector_controller, EigerDetectorController)

    attr: AttrRW = detector_controller.attributes["threshold_1_energy"]  # type: ignore

    queue_update_spy = mocker.spy(detector_controller, "queue_update")

    # make sure API inconsistency for threshold/difference/mode is addressed
    attr: AttrRW = detector_controller.attributes["threshold_difference_mode"]  # type: ignore
    sender: EigerConfigHandler = attr.sender  # type: ignore
    assert sender is not None

    api_put_response = await controller.connection.put(sender.uri, "enabled")
    assert api_put_response == ["difference_mode"]
    # would expect threshold/difference/mode but Eiger API 1.8.0 has this inconsistency

    await sender.put(detector_controller, attr, "enabled")
    queue_update_spy.assert_called_with(["threshold/difference/mode"])
    await detector_controller.connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sim_eiger_controller", [str(HERE / "eiger.yaml")], indirect=True
)
async def test_fetch_before_returning_parameters(
    sim_eiger_controller: EigerController, mocker: MockerFixture
):
    controller = sim_eiger_controller
    await controller.initialise()
    detector_controller = controller.get_sub_controllers()["Detector"]
    assert isinstance(detector_controller, EigerDetectorController)

    count_time_attr = detector_controller.attributes.get("count_time")
    bit_depth_image_attr = detector_controller.attributes.get("bit_depth_image")
    assert isinstance(count_time_attr, AttrRW)
    assert isinstance(bit_depth_image_attr, AttrR)
    count_time_spy = mocker.spy(count_time_attr.updater, "config_update")
    bit_depth_image_spy = mocker.spy(bit_depth_image_attr.updater, "config_update")
    queue_update_spy = mocker.spy(detector_controller, "queue_update")
    update_now_spy = mocker.spy(detector_controller, "update_now")
    controller_update_spy = mocker.spy(controller, "update")

    assert isinstance(count_time_attr.updater, EigerConfigHandler)
    await count_time_attr.updater.put(detector_controller, count_time_attr, 2)

    update_now_spy.assert_awaited_once_with(["bit_depth_image", "bit_depth_readout"])

    # bit_depth_image and bit_depth_readout handled early
    queue_update_spy.assert_awaited_once_with(
        [
            "count_time",
            "countrate_correction_count_cutoff",
            "frame_count_time",
            "frame_time",
        ]
    )
    count_time_spy.assert_not_awaited()
    bit_depth_image_spy.assert_awaited()
    controller_update_spy.assert_not_awaited()

    await controller.update()
    count_time_spy.assert_called()

    await controller.connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sim_eiger_controller", [str(HERE / "eiger.yaml")], indirect=True
)
async def test_stale_propagates_to_top_controller(
    sim_eiger_controller: EigerController,
):
    controller = sim_eiger_controller
    await controller.initialise()
    detector_controller = controller.get_sub_controllers()["Detector"]
    assert isinstance(detector_controller, EigerDetectorController)
    await detector_controller.queue_update(["threshold_energy"])
    assert controller.stale_parameters.get() is True
    # top controller should be set to stale
    assert not controller.queue.empty()
    await controller.update()
    assert controller.queue.empty()
    assert controller.stale_parameters.get() is False

    await detector_controller.queue_update(
        ["nonexistent_parameter"]
    )  # only gets set to stale if there's a real attribute update to queue...
    assert controller.stale_parameters.get() is False
    assert controller.queue.empty()

    await controller.connection.close()


@pytest.mark.asyncio
async def test_attribute_validation_raises_for_invalid_type(mock_connection):
    eiger_controller, connection = mock_connection
    connection.get.return_value = {
        "access_mode": "r",
        "allowed_values": None,
        "value": "test_value",
        "value_type": "invalid_type",
    }
    with pytest.raises(ValidationError) as e:
        await eiger_controller.initialise()

    error_msg = str(e.value)
    assert "Input should be" in error_msg and all(
        f"'{t}'" in error_msg for t in EIGER_PARAMETER_VALID_VALUES
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_type", EIGER_PARAMETER_VALID_VALUES)
async def test_attribute_validation_accepts_valid_types(mock_connection, valid_type):
    eiger_controller, connection = mock_connection
    connection.get.return_value = {
        "access_mode": "r",
        "allowed_values": None,
        "value": "test_value",
        "value_type": valid_type,
    }

    await eiger_controller.initialise()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sim_eiger_controller", [str(HERE / "eiger.yaml")], indirect=True
)
async def test_eiger_controller_trigger(
    mocker: MockerFixture, sim_eiger_controller: EigerController
):
    controller = sim_eiger_controller
    controller.connection.put = mocker.AsyncMock()
    await controller.initialise()

    detector_controller = controller.get_sub_controllers()["Detector"]
    assert isinstance(detector_controller, EigerDetectorController)

    await detector_controller.trigger_mode.set("inte")

    # Checking that 'trigger_mode' in attributes is also the internal attribute
    # https://github.com/DiamondLightSource/fastcs-eiger/issues/65
    assert detector_controller.attributes["trigger_mode"].get() == "inte"  # type: ignore

    await detector_controller.trigger_exposure.set(0.1)
    await detector_controller.trigger()
