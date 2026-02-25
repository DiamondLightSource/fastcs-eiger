from fastcs_eiger.eiger_parameter import EigerParameterRef, EigerParameterResponse


def test_eiger_access_mode():

    ref = EigerParameterRef(
        key="dummy_uri",
        subsystem="detector",
        api_version="1.8.0",
        mode="config",
        response=EigerParameterResponse(access_mode="r", value=0.0, value_type="float"),
    )
    assert ref.access_mode == "r"

    ref = EigerParameterRef(
        key="dummy_uri",
        subsystem="detector",
        api_version="1.8.0",
        mode="status",
        response=EigerParameterResponse(
            access_mode="rw", value=0.0, value_type="float"
        ),
    )
    assert ref.access_mode == "rw"

    ref = EigerParameterRef(
        key="dummy_uri",
        subsystem="detector",
        api_version="1.6.0",
        mode="status",
        response=EigerParameterResponse(
            access_mode=None, value=0.0, value_type="float"
        ),
    )
    assert ref.access_mode == "r"

    ref = EigerParameterRef(
        key="dummy_uri",
        subsystem="detector",
        api_version="1.6.0",
        mode="config",
        response=EigerParameterResponse(
            access_mode=None, value=0.0, value_type="float"
        ),
    )
    assert ref.access_mode == "rw"
