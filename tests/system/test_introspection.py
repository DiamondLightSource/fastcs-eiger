import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastcs.attributes import Attribute, AttrR, AttrRW
from fastcs.datatypes import Float
from pydantic import ValidationError
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_controller import EigerController
from fastcs_eiger.eiger_detector_controller import EigerDetectorController
from fastcs_eiger.eiger_monitor_controller import EigerMonitorController
from fastcs_eiger.eiger_parameter import EigerParameterRef, EigerParameterResponse
from fastcs_eiger.eiger_stream_controller import EigerStreamController
from fastcs_eiger.eiger_subsystem_controller import (
    IGNORED_KEYS,
    MISSING_KEYS,
    EigerSubsystemController,
)

HERE = Path(__file__).parent

EIGER_PARAMETER_VALID_VALUES = EigerParameterResponse.__annotations__[
    "value_type"
].__args__


def _serialise_parameter(parameter: EigerParameterRef) -> dict:
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
        subcontroller = controller.sub_controllers[subsystem.title()]
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
async def test_threshold_mode_api_inconsistency_handled(
    sim_eiger_controller: EigerController, mocker: MockerFixture
):
    controller = sim_eiger_controller
    await controller.initialise()

    detector_controller = controller.sub_controllers["Detector"]
    assert isinstance(detector_controller, EigerDetectorController)

    attr: AttrRW = detector_controller.attributes["threshold_1_energy"]  # type: ignore

    queue_update_spy = mocker.spy(detector_controller._io, "queue_update")

    # make sure API inconsistency for threshold/difference/mode is addressed
    attr: AttrRW[str, EigerParameterRef] = detector_controller.attributes[
        "threshold_difference_mode"
    ]  # type: ignore

    api_put_response = await controller.connection.put(attr.io_ref.uri, "enabled")
    assert api_put_response == ["difference_mode"]
    # would expect threshold/difference/mode but Eiger API 1.8.0 has this inconsistency

    await detector_controller._io.send(attr, "enabled")
    queue_update_spy.assert_called_with(["threshold/difference/mode"])
    await controller.update()
    assert attr.get() == "enabled"
    await detector_controller.connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sim_eiger_controller", [str(HERE / "eiger.yaml")], indirect=True
)
async def test_fetch_before_returning_parameters(
    sim_eiger_controller: EigerController, mocker: MockerFixture
):
    # Need to mock @scan to spy controller.update()
    with patch("fastcs_eiger.eiger_controller.scan"):
        controller = sim_eiger_controller
        await controller.initialise()

        detector_controller = controller.sub_controllers["Detector"]
        assert isinstance(detector_controller, EigerDetectorController)

        count_time_attr: AttrRW[float, EigerParameterRef] = (
            detector_controller.attributes.get("count_time")
        )  # type: ignore
        count_time_attr.io_ref.update_period = None
        frame_time_attr = detector_controller.attributes.get("frame_time")
        bit_depth_image_attr = detector_controller.attributes.get("bit_depth_image")
        assert isinstance(count_time_attr, AttrRW)
        assert isinstance(frame_time_attr, AttrRW)
        assert isinstance(bit_depth_image_attr, AttrR)

        queue_update_spy = mocker.spy(detector_controller._io, "queue_update")
        update_now_spy = mocker.spy(detector_controller._io, "update_now")
        io_do_update_spy = mocker.spy(detector_controller._io, "do_update")
        await detector_controller._io.send(count_time_attr, 2.0)

        # bit_depth_image and bit_depth_readout handled early
        update_now_spy.assert_awaited_once_with(
            ["bit_depth_image", "bit_depth_readout"]
        )

        queue_update_spy.assert_awaited_once_with(
            [
                "count_time",
                "countrate_correction_count_cutoff",
                "frame_count_time",
                "frame_time",
            ]
        )

        updated = [call.args[0].io_ref.key for call in io_do_update_spy.await_args_list]
        assert "bit_depth_image" in updated
        assert "count_time" not in updated

        # queued updated not updated until controller.update()
        await controller.update()
        updated = [call.args[0].io_ref.key for call in io_do_update_spy.await_args_list]
        assert "count_time" in updated

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

    detector_controller = controller.sub_controllers["Detector"]
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
async def test_eiger_controller_trigger_correctly_introspected(
    mocker: MockerFixture, sim_eiger_controller: EigerController
):
    controller = sim_eiger_controller
    await controller.initialise()

    detector_controller = controller.sub_controllers["Detector"]
    assert isinstance(detector_controller, EigerDetectorController)
    detector_controller.connection = mocker.AsyncMock()

    await detector_controller.trigger_mode.update("inte")

    # Checking that 'trigger_mode' in attributes is also the internal attribute
    # https://github.com/DiamondLightSource/fastcs-eiger/issues/65
    assert detector_controller.attributes["trigger_mode"].get() == "inte"  # type: ignore

    await detector_controller.trigger_exposure.update(0.1)
    await detector_controller.trigger()

    await detector_controller.queue_update(["nonexistent_parameter"])

    await controller.connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_min, expected_prec",
    [
        [0.0001, 4],
        [0.001, 3],
        [0.01, 2],
        [0.1, 1],
        [1, 2],  # Case where min is int.
        [123.123, 3],
        [0, 2],
        [0.0, 1],
        [1e-5, 5],
        [1e5, 1],
        [None, 2],
    ],
)
async def test_if_min_value_provided_then_prec_set_correctly(
    mock_min, expected_prec, mock_connection
):
    eiger_controller, connection = mock_connection

    connection.get.side_effect = [
        {"value": "test_state_val"},
        ["test_float_attr"],
        {
            "access_mode": "r",
            "allowed_values": None,
            "value": 1.0,
            "value_type": "float",
            "min": mock_min,
        },
        {
            "access_mode": "r",
            "allowed_values": None,
            "value": "test_error_value",
            "value_type": "string[]",
        },  # Second dict populates missing stream key.
    ]

    with (
        patch("fastcs_eiger.eiger_controller.EIGER_PARAMETER_SUBSYSTEMS", ["detector"]),
        patch(
            "fastcs_eiger.eiger_subsystem_controller.EIGER_PARAMETER_MODES", ["status"]
        ),
    ):
        await eiger_controller.initialise()

    test_float_attr = eiger_controller.sub_controllers["Detector"].attributes.get(
        "test_float_attr"
    )

    assert test_float_attr.datatype == Float(prec=expected_prec)
