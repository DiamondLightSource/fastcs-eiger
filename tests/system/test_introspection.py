import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastcs.attributes import Attribute, AttrR, AttrRW
from fastcs.datatypes import Float
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_controller import (
    IGNORED_KEYS,
    MISSING_KEYS,
    EigerConfigHandler,
    EigerController,
    EigerDetectorController,
    EigerMonitorController,
    EigerParameter,
    EigerStreamController,
    EigerSubsystemController,
)

HERE = Path(__file__).parent


def _serialise_parameter(parameter: EigerParameter) -> dict:
    return {
        "subsystem": parameter.subsystem,
        "mode": parameter.mode,
        "key": parameter.key,
        "response": {
            k: v
            for k, v in parameter.response.items()
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
            attr: AttrRW = subcontroller.attributes["threshold_1_energy"]  # type: ignore

            subcontroller.queue_update = AsyncMock()

            sender = attr.sender
            assert sender is not None
            await sender.put(subcontroller, attr, 100.0)
            # set parameters to update based on response to put request
            subcontroller.queue_update.assert_called_with(
                [
                    "flatfield",
                    "threshold/1/energy",
                    "threshold/1/flatfield",
                    "threshold/2/flatfield",
                    "threshold_energy",
                ]
            )

            # make sure API inconsistency for threshold/difference/mode is addressed
            attr: AttrRW = subcontroller.attributes["threshold_difference_mode"]  # type: ignore
            sender = attr.sender
            assert sender is not None
            await sender.put(subcontroller, attr, "enabled")
            subcontroller.queue_update.assert_called_with(["threshold/difference/mode"])

        for keys in MISSING_KEYS[subsystem].values():  # loop over status, config keys
            for key in keys:
                assert any(param.key == key for param in parameters)

    await controller.connection.close()


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

    assert not detector_controller._parameter_updates
    assert isinstance(count_time_attr.updater, EigerConfigHandler)
    await count_time_attr.updater.put(detector_controller, count_time_attr, 2)
    to_update: set[str] = detector_controller._parameter_updates
    assert (
        to_update
        and "bit_depth_image" not in to_update
        and "bit_depth_readout" not in to_update
    )

    count_time_spy.assert_not_called()
    bit_depth_image_spy.assert_called()

    await detector_controller.update()
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
