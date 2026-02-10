from pathlib import Path
from unittest.mock import MagicMock, call, patch

import h5py
import numpy as np
import pytest

from fastcs_eiger.controllers.odin.generate_vds import (
    create_interleave_vds,
    get_frames_per_file_writer,
)


@pytest.mark.parametrize(
    "frame_count, frames_per_block, n_file_writers, expected_split_frames",
    [
        [10, 1, 3, [4, 3, 3]],
        [10, 1, 10, [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]],
        [10, 4, 10, [4, 4, 2, 0, 0, 0, 0, 0, 0, 0]],
        [10, 1, 1, [10]],
        [10, 4, 2, [6, 4]],
        [10, 4, 3, [4, 4, 2]],
        [10, 3, 3, [4, 3, 3]],
        [105, 10, 4, [30, 30, 25, 20]],
        [1000000, 500, 4, [250000, 250000, 250000, 250000]],
    ],
)
def test_get_frames_per_file_splits_frames_correctly(
    frame_count: int,
    frames_per_block: int,
    n_file_writers: int,
    expected_split_frames: list[int],
):
    split_frames_numbers = get_frames_per_file_writer(
        frame_count, frames_per_block, n_file_writers
    )
    assert split_frames_numbers == expected_split_frames


@pytest.mark.parametrize(
    "frame_count, frames_per_block, blocks_per_file, n_file_writers, expected_files",
    [
        [100, 10, 5, 1, {b"test_000001.h5", b"test_000002.h5"}],
        [105, 10, 5, 1, {b"test_000001.h5", b"test_000002.h5", b"test_000003.h5"}],
        [
            25,
            5,
            1,
            4,
            {
                b"test_000001.h5",
                b"test_000002.h5",
                b"test_000003.h5",
                b"test_000004.h5",
                b"test_000005.h5",
            },
        ],
        [105, 10, 0, 1, {b"test_000001.h5"}],
        [1000, 2, 0, 1, {b"test_000001.h5"}],
        [
            100,
            10,
            3,
            2,
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
    n_file_writers: int,
    expected_files: set[str],
):
    mock_file = MagicMock()
    mock_f = MagicMock()
    mock_file.__enter__.return_value = mock_f
    with patch(
        "fastcs_eiger.controllers.odin.generate_vds.h5py.File", return_value=mock_file
    ):
        create_interleave_vds(
            Path(),
            "test",
            frame_count,
            frames_per_block,
            blocks_per_file,
            (1, 1),
            n_file_writers=n_file_writers,
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
    create_interleave_vds(Path(), "test", 105, 10, 3, (10, 10))
    expected_split_frames = [30, 30, 25, 20]
    assert len(mock_virtual_source.call_args_list) == 4
    for i, expected_frames in enumerate(expected_split_frames):
        assert mock_virtual_source.call_args_list[i] == call(
            f"test_00000{i + 1}.h5",
            name="data",
            shape=(expected_frames, 10, 10),
            dtype="float",
        )


@pytest.fixture
def mock_round_robin_data() -> tuple[list[np.ndarray], np.ndarray]:
    """Assuming 4 file writers, blocks of 2 frames, and 2 blocks per file."""
    file1_data = np.array(
        [
            [[0, 0], [0, 0]],
            [[1, 1], [1, 1]],
            [[8, 8], [8, 8]],
            [[9, 9], [9, 9]],
        ]
    )
    file2_data = np.array(
        [
            [[2, 2], [2, 2]],
            [[3, 3], [3, 3]],
            [[10, 10], [10, 10]],
            [[11, 11], [11, 11]],
        ]
    )
    file3_data = np.array(
        [
            [[4, 4], [4, 4]],
            [[5, 5], [5, 5]],
            [[12, 12], [12, 12]],
            [[13, 13], [13, 13]],
        ]
    )
    file4_data = np.array(
        [
            [[6, 6], [6, 6]],
            [[7, 7], [7, 7]],
            [[14, 14], [14, 14]],
            [[15, 15], [15, 15]],
        ]
    )
    file5_data = np.array(
        [
            [[16, 16], [16, 16]],
            [[17, 17], [17, 17]],
        ]
    )
    file6_data = np.array(
        [
            [[18, 18], [18, 18]],
        ]
    )

    expected_vds_data = np.array(
        [
            [[0, 0], [0, 0]],
            [[1, 1], [1, 1]],
            [[2, 2], [2, 2]],
            [[3, 3], [3, 3]],
            [[4, 4], [4, 4]],
            [[5, 5], [5, 5]],
            [[6, 6], [6, 6]],
            [[7, 7], [7, 7]],
            [[8, 8], [8, 8]],
            [[9, 9], [9, 9]],
            [[10, 10], [10, 10]],
            [[11, 11], [11, 11]],
            [[12, 12], [12, 12]],
            [[13, 13], [13, 13]],
            [[14, 14], [14, 14]],
            [[15, 15], [15, 15]],
            [[16, 16], [16, 16]],
            [[17, 17], [17, 17]],
            [[18, 18], [18, 18]],
        ]
    )
    return [
        file1_data,
        file2_data,
        file3_data,
        file4_data,
        file5_data,
        file6_data,
    ], expected_vds_data


def test_create_interleave_vds_before_files_written(
    tmp_path,
    mock_round_robin_data: tuple[list[np.ndarray], np.ndarray],
):
    acquired_data, expected_vds_data = mock_round_robin_data
    prefix = "test"

    create_interleave_vds(tmp_path, prefix, 19, 2, 2, (2, 2))

    for i, data in enumerate(acquired_data):
        with h5py.File(tmp_path / f"test_00000{i + 1}.h5", "w") as f:
            f.create_dataset(name="data", data=data)

    with h5py.File(f"{tmp_path / prefix}_vds.h5", "r") as f:
        virtual_dataset = f.get("data")
        assert isinstance(virtual_dataset, h5py.Dataset)
        result = virtual_dataset[()]

    assert np.array_equal(result, expected_vds_data)


def test_create_interleave_vds_after_files_written(
    tmp_path,
    mock_round_robin_data: tuple[list[np.ndarray], np.ndarray],
):
    acquired_data, expected_vds_data = mock_round_robin_data
    prefix = "test"

    for i, data in enumerate(acquired_data):
        with h5py.File(tmp_path / f"test_00000{i + 1}.h5", "w") as f:
            f.create_dataset(name="data", data=data)

    create_interleave_vds(tmp_path, prefix, 19, 2, 2, (2, 2))

    with h5py.File(f"{tmp_path / prefix}_vds.h5", "r") as f:
        virtual_dataset = f.get("data")
        assert isinstance(virtual_dataset, h5py.Dataset)
        result = virtual_dataset[()]

    assert np.array_equal(result, expected_vds_data)
