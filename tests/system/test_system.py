from pathlib import Path

import pytest
from fastcs.attributes import Attribute

from fastcs_eiger.eiger_controller import IGNORED_KEYS, MISSING_KEYS, EigerController

HERE = Path(__file__).parent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sim_eiger_controller", [str(HERE / "eiger.yaml")], indirect=True
)
async def test_controller_groups_and_parameters(sim_eiger_controller: EigerController):
    controller = sim_eiger_controller
    await controller.initialise()

    for subsystem in MISSING_KEYS:
        subcontroller = controller.get_sub_controllers()[subsystem.title()]
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

            attr = subcontroller.threshold_1_energy
            sender = attr.sender
            await sender.put(subcontroller, attr, 100.0)
            # set parameters to update based on response to put request
            assert subcontroller._parameter_updates == {
                "flatfield",
                "threshold/1/energy",
                "threshold/1/flatfield",
                "threshold/2/flatfield",
                "threshold_energy",
            }

            subcontroller._parameter_updates.clear()

            # make sure API inconsistency for threshold/difference/mode is addressed
            attr = subcontroller.threshold_difference_mode
            sender = attr.sender
            await sender.put(subcontroller, attr, "enabled")
            assert subcontroller._parameter_updates == {"threshold/difference/mode"}

        for keys in MISSING_KEYS[subsystem].values():  # loop over status, config keys
            for key in keys:
                assert any(param.key == key for param in parameters)

    await controller.connection.close()
