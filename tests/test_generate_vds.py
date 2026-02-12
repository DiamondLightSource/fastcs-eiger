from pathlib import Path
from unittest.mock import MagicMock, patch

import h5py
import numpy as np
import pytest

from fastcs_eiger.controllers.odin.generate_vds import (
    FileFrames,
    _calculate_frame_distribution,
    _get_frames_per_file_writer,
    create_interleave_vds,
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
def test_get_frames_per_file_writer_splits_frames_correctly(
    frame_count: int,
    frames_per_block: int,
    n_file_writers: int,
    expected_split_frames: list[int],
):
    split_frames_numbers = _get_frames_per_file_writer(
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
        [1000, 2, 0, 2, {b"test_000001.h5", b"test_000002.h5"}],
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
            ["data"],
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
@pytest.mark.parametrize(
    "frame_count, frames_per_block, blocks_per_file, expected_frames_per_file",
    [
        [155, 10, 3, [30, 30, 30, 30, 10, 10, 10, 5]],
        [145, 10, 3, [30, 30, 30, 30, 10, 10, 5]],
        [145, 10, 0, [40, 40, 35, 30]],
        [145, 1, 0, [37, 36, 36, 36]],
        [20, 30, 0, [20]],
    ],
)
def test_create_interleave_cds_makes_expected_source_layout_calls(
    mock_file: MagicMock,
    mock_virtual_layoud: MagicMock,
    mock_virtual_source: MagicMock,
    frame_count: int,
    frames_per_block: int,
    blocks_per_file: int,
    expected_frames_per_file: list[int],
):
    datasets = ["data", "sets"]
    create_interleave_vds(
        Path(),
        "test",
        datasets,
        frame_count,
        frames_per_block,
        blocks_per_file,
        (10, 10),
    )
    assert len(mock_virtual_source.call_args_list) == len(
        expected_frames_per_file
    ) * len(datasets)
    for dataset_name in datasets:
        for i, expected_frames in enumerate(expected_frames_per_file):
            mock_virtual_source.assert_any_call(
                f"test_00000{i + 1}.h5",
                name=dataset_name,
                shape=(expected_frames, 10, 10),
                dtype="float",
            )


@pytest.mark.parametrize(
    "frames, frames_per_block, expected_blocks, expected_remainder",
    [[6, 3, 2, 0], [8, 3, 2, 2], [6, 7, 0, 6], [6, 6, 1, 0]],
)
def test_file_frames_dataclass_calculates_blocks_and_remainder_correctly(
    frames: int, frames_per_block: int, expected_blocks, expected_remainder
):
    file_frames = FileFrames(frames=frames, frames_per_block=frames_per_block, start=0)
    assert file_frames.blocks == expected_blocks
    assert file_frames.remainder_frames == expected_remainder


@pytest.mark.parametrize(
    "frame_count, frames_per_block, blocks_per_file, n_writers, expected_distribution",
    [
        [
            10,
            3,
            2,
            1,
            {
                1: FileFrames(frames=6, frames_per_block=3, start=0),
                2: FileFrames(frames=4, frames_per_block=3, start=6),
            },
        ],
        [10, 10, 0, 4, {1: FileFrames(frames=10, frames_per_block=10, start=0)}],
        [
            985,
            10,
            0,
            4,
            {
                1: FileFrames(frames=250, frames_per_block=10, start=0),
                2: FileFrames(frames=250, frames_per_block=10, start=10),
                3: FileFrames(frames=245, frames_per_block=10, start=20),
                4: FileFrames(frames=240, frames_per_block=10, start=30),
            },
        ],
        [
            19,
            2,
            2,
            4,
            {
                1: FileFrames(frames=4, frames_per_block=2, start=0),
                2: FileFrames(frames=4, frames_per_block=2, start=2),
                3: FileFrames(frames=4, frames_per_block=2, start=4),
                4: FileFrames(frames=4, frames_per_block=2, start=6),
                5: FileFrames(frames=2, frames_per_block=2, start=16),
                6: FileFrames(frames=1, frames_per_block=2, start=18),
            },
        ],
    ],
)
def test_calculate_frame_distribution(
    frame_count: int,
    frames_per_block: int,
    blocks_per_file: int,
    n_writers: int,
    expected_distribution: dict[int, FileFrames],
):
    result = _calculate_frame_distribution(
        frame_count, frames_per_block, blocks_per_file, n_writers
    )
    assert result == expected_distribution


@pytest.fixture
def mock_round_robin_data() -> tuple[list[np.ndarray], np.ndarray]:
    """Assuming 4 file writers, 19 frames in blocks of 2 frames, and  2 blocks per file.
    Frames are 2 x 2. The values in each frame represent the order they would have been
    written in, and therefore the order the VDS should splice them together in."""
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

    create_interleave_vds(tmp_path, prefix, ["data"], 19, 2, 2, (2, 2))

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

    create_interleave_vds(tmp_path, prefix, ["data"], 19, 2, 2, (2, 2))

    with h5py.File(f"{tmp_path / prefix}_vds.h5", "r") as f:
        virtual_dataset = f.get("data")
        assert isinstance(virtual_dataset, h5py.Dataset)
        result = virtual_dataset[()]

    assert np.array_equal(result, expected_vds_data)


def test_create_interleave_vds_creates_virtual_dataset_for_all_datasets(
    tmp_path,
    mock_round_robin_data: tuple[list[np.ndarray], np.ndarray],
):
    acquired_data, expected_vds_data = mock_round_robin_data
    prefix = "test"

    for i, data in enumerate(acquired_data):
        with h5py.File(tmp_path / f"test_00000{i + 1}.h5", "w") as f:
            f.create_dataset(name="one", data=np.zeros(data.shape))
            f.create_dataset(name="two", data=data * 10)
            f.create_dataset(name="three", data=data * 100)

    create_interleave_vds(tmp_path, prefix, ["one", "two", "three"], 19, 2, 2, (2, 2))

    with h5py.File(f"{tmp_path / prefix}_vds.h5", "r") as f:
        assert np.array_equal(f.get("one")[()], np.zeros(expected_vds_data.shape))  # type: ignore
        assert np.array_equal(f.get("two")[()], expected_vds_data * 10)  # type: ignore
        assert np.array_equal(f.get("three")[()], expected_vds_data * 100)  # type: ignore
