import os
from typing import Any

import pytest

# Prevent pytest from catching exceptions when debugging in vscode so that break on
# exception works correctly (see: https://github.com/pytest-dev/pytest/issues/7409)
if os.getenv("PYTEST_RAISE", "0") == "1":

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call: pytest.CallInfo[Any]):
        if call.excinfo is not None:
            raise call.excinfo.value
        else:
            raise RuntimeError(
                f"{call} has no exception data, an unknown error has occurred"
            )

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo: pytest.ExceptionInfo[Any]):
        raise excinfo.value


_detector_config_keys = [
    "auto_summation",
    "beam_center_x",
    "beam_center_y",
    "bit_depth_image",
    "bit_depth_readout",
    "chi_increment",
    "chi_start",
    "compression",
    "count_time",
    "counting_mode",
    "countrate_correction_applied",
    "countrate_correction_count_cutoff",
    "data_collection_date",
    "description",
    "detector_distance",
    "detector_number",
    "detector_readout_time",
    "eiger_fw_version",
    "element",
    "extg_mode",
    "fast_arm",
    "flatfield_correction_applied",
    "frame_count_time",
    "frame_time",
    "incident_energy",
    "incident_particle_type",
    "instrument_name",
    "kappa_increment",
    "kappa_start",
    "mask_to_zero",
    "nexpi",
    "nimages",
    "ntrigger",
    "ntriggers_skipped",
    "number_of_excluded_pixels",
    "omega_increment",
    "omega_start",
    "phi_increment",
    "phi_start",
    "photon_energy",
    "pixel_mask_applied",
    "roi_mode",
    "sample_name",
    "sensor_material",
    "sensor_thickness",
    "software_version",
    "source_name",
    "threshold/1/energy",
    "threshold/1/mode",
    "threshold/1/number_of_excluded_pixels",
    "threshold/2/energy",
    "threshold/2/mode",
    "threshold/2/number_of_excluded_pixels",
    "threshold/difference/lower_threshold",
    "threshold/difference/mode",
    "threshold/difference/upper_threshold",
    "threshold_energy",
    "total_flux",
    "trigger_mode",
    "trigger_start_delay",
    "two_theta_increment",
    "two_theta_start",
    "virtual_pixel_correction_applied",
    "x_pixel_size",
    "x_pixels_in_detector",
    "y_pixel_size",
    "y_pixels_in_detector",
]

_detector_status_keys = [
    "humidity",
    "link_0",
    "link_1",
    "series_unique_id",
    "state",
    "temperature",
    "time",
]

_stream_config_keys = [
    "format",
    "header_appendix",
    "header_detail",
    "image_appendix",
    "mode",
]
_stream_status_keys = ["dropped", "state"]
_monitor_config_keys = ["buffer_size", "discard_new", "mode"]
_monitor_status_keys = ["buffer_free", "dropped", "error", "state"]


@pytest.fixture
def detector_config_keys() -> list[str]:
    return _detector_config_keys


@pytest.fixture
def detector_status_keys():
    return _detector_status_keys


@pytest.fixture
def monitor_config_keys():
    return _monitor_config_keys


@pytest.fixture
def monitor_status_keys():
    return _monitor_status_keys


@pytest.fixture
def stream_config_keys():
    return _stream_config_keys


@pytest.fixture
def stream_status_keys():
    return _stream_status_keys


@pytest.fixture
def keys_mapping() -> dict[str, list[str]]:
    return {
        "detector/api/1.8.0/status/keys": _detector_status_keys,
        "detector/api/1.8.0/config/keys": _detector_config_keys,
        "monitor/api/1.8.0/status/keys": _monitor_status_keys,
        "monitor/api/1.8.0/config/keys": _monitor_config_keys,
        "stream/api/1.8.0/status/keys": _stream_status_keys,
        "stream/api/1.8.0/config/keys": _stream_config_keys,
    }


@pytest.fixture
def put_response_mapping() -> dict[str, list[str]]:
    time_keys = [
        "bit_depth_image",
        "bit_depth_readout",
        "count_time",
        "countrate_correction_count_cutoff",
        "frame_count_time",
        "frame_time",
    ]
    energy_keys = [
        "element",
        "flatfield",
        "incident_energy",
        "photon_energy",
        "threshold/1/energy",
        "threshold/1/flatfield",
        "threshold/2/energy",
        "threshold/2/flatfield",
        "threshold_energy",
        "wavelength",
    ]
    threshold_energy_keys = [
        "flatfield",
        "threshold/1/energy",
        "threshold/1/flatfield",
        "threshold/2/flatfield",
        "threshold_energy",
    ]
    return {
        "auto_summation": ["auto_summation", "frame_count_time"],
        "count_time": time_keys,
        "frame_time": time_keys,
        "flatfield": ["flatfield", "threshold/1/flatfield"],
        "incident_energy": energy_keys,
        "photon_energy": energy_keys,
        "pixel_mask": ["pixel_mask", "threshold/1/pixel_mask"],
        "threshold/1/flatfield": ["flatfield", "threshold/1/flatfield"],
        "roi_mode": ["count_time", "frame_time", "roi_mode"],
        "threshold_energy": threshold_energy_keys,
        "threshold/1/energy": threshold_energy_keys,
        "threshold/2/energy": [
            "flatfield",
            "threshold/1/flatfield",
            "threshold/2/energy",
            "threshold/2/flatfield",
        ],
        "threshold/1/mode": ["threshold/1/mode", "threshold/difference/mode"],
        "threshold/2/mode": ["threshold/2/mode", "threshold/difference/mode"],
        "threshold/1/pixel_mask": ["pixel_mask", "threshold/1/pixel_mask"],
        "threshold/difference/mode": ["difference_mode"],
        # replicating API inconsistency
    }
