from unittest.mock import MagicMock, call, patch

import h5py
import pytest

from fastcs_eiger.controllers.odin.generate_vds import (
    create_interleave_vds,
    get_split_frame_numbers,
)


@pytest.mark.parametrize(
    "frame_count, frames_per_block, n_files, expected_split_frames",
    [
        [10, 1, 3, [4, 3, 3]],
        [10, 1, 10, [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]],
        [10, 4, 10, [4, 4, 2, 0, 0, 0, 0, 0, 0, 0]],
        [10, 1, 1, [10]],
        [10, 4, 2, [6, 4]],
        [10, 4, 3, [4, 4, 2]],
        [10, 3, 3, [4, 3, 3]],
        [105, 10, 3, [40, 35, 30]],
        [1000000, 500, 4, [250000, 250000, 250000, 250000]],
    ],
)
def test_get_split_frame_numbers_splits_frames_correctly(
    frame_count: int,
    frames_per_block: int,
    n_files: int,
    expected_split_frames: list[int],
):
    split_frames_numbers = get_split_frame_numbers(
        frame_count, frames_per_block, n_files
    )
    assert split_frames_numbers == expected_split_frames


@pytest.mark.parametrize(
    "frame_count, frames_per_block, blocks_per_file, expected_files",
    [
        [100, 10, 5, {b"test_000001.h5", b"test_000002.h5"}],
        [105, 10, 5, {b"test_000001.h5", b"test_000002.h5", b"test_000003.h5"}],
        [25, 10, 1, {b"test_000001.h5", b"test_000002.h5", b"test_000003.h5"}],
        [105, 10, 0, {b"test_000001.h5"}],
        [1000, 2, 0, {b"test_000001.h5"}],
        [
            100,
            10,
            3,
            {
                b"test_000001.h5",
                b"test_000002.h5",
                b"test_000003.h5",
                b"test_000004.h5",
            },
        ],
    ],
)
def test_create_interleave_vds_layout_contains_expected_files_and_has_expected_shape(
    frame_count: int,
    frames_per_block: int,
    blocks_per_file: int,
    expected_files: set[str],
):
    mock_file = MagicMock()
    mock_f = MagicMock()
    mock_file.__enter__.return_value = mock_f
    with patch(
        "fastcs_eiger.controllers.odin.generate_vds.h5py.File", return_value=mock_file
    ):
        create_interleave_vds(
            "test", frame_count, frames_per_block, blocks_per_file, (1, 1)
        )
    layout: h5py.VirtualLayout = mock_f.create_virtual_dataset.call_args[0][1]
    assert layout._src_filenames == expected_files
    assert layout.shape == (frame_count, 1, 1)


@patch("fastcs_eiger.controllers.odin.generate_vds.h5py.VirtualSource")
@patch("fastcs_eiger.controllers.odin.generate_vds.h5py.VirtualLayout")
@patch("fastcs_eiger.controllers.odin.generate_vds.h5py.File")
def test_create_interleave_cds_makes_expected_source_layout_calls(
    mock_file: MagicMock, mock_virtual_layoud: MagicMock, mock_virtual_source: MagicMock
):
    create_interleave_vds("test.h5", 105, 10, 3, (10, 10))
    expected_split_frames = [30, 30, 25, 20]
    assert len(mock_virtual_source.call_args_list) == 4
    for i, expected_frames in enumerate(expected_split_frames):
        assert mock_virtual_source.call_args_list[i] == call(
            f"test_00000{i + 1}.h5",
            name="data",
            shape=(expected_frames, 10, 10),
            dtype="float",
        )
