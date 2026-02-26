import pytest

from fastcs_eiger.eiger_parameter import EigerParameterRef, EigerParameterResponse


@pytest.mark.parametrize(
    "api_version, mode, response_access_mode, expected_access_mode",
    [
        ("1.8.0", "config", "r", "r"),  # If access_mode exists, mode ignored
        ("1.8.0", "status", "rw", "rw"),
        ("1.6.0", "status", None, "r"),  # If no access_mode, infer from mode
        ("1.6.0", "config", None, "rw"),
    ],
)
def test_eiger_access_mode(
    api_version, mode, response_access_mode, expected_access_mode
):
    ref = EigerParameterRef(
        key="dummy_uri",
        subsystem="detector",
        api_version=api_version,
        mode=mode,
        response=EigerParameterResponse(
            access_mode=response_access_mode, value=0.0, value_type="float"
        ),
    )
    assert ref.access_mode == expected_access_mode
