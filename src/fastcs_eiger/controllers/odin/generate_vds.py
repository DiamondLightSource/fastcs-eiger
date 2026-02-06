import math
from pathlib import Path

import h5py
import numpy as np


def create_interleave_vds(
    path: str,
    frame_count: int,
    frames_per_block: int,
    blocks_per_file: int,
    frame_shape: tuple[int, int],
) -> None:
    dtype = "float"
    dataset_name = "data"
    frames_per_file = min(
        (frames_per_block * blocks_per_file if blocks_per_file else frame_count),
        frame_count,
    )
    n_files = math.ceil(frame_count / frames_per_file)

    file_name_prefix = Path(path).with_suffix("")
    filepaths = [f"{file_name_prefix}_{str(i + 1).zfill(6)}.h5" for i in range(n_files)]

    min_frames_per_file = frames_per_file - frames_per_block
    remainder = frame_count - (min_frames_per_file * n_files)

    v_layout = h5py.VirtualLayout(
        shape=(frame_count, frame_shape[0], frame_shape[1]),
        dtype=dtype,
    )

    for file_idx, filepath in enumerate(filepaths):
        remaining = max(remainder - (frames_per_block * file_idx), 0)
        frames_in_file = min_frames_per_file + min(frames_per_block, remaining)
        block_remainder = frames_in_file % frames_per_block

        # MultiBlockSlice cannot contain partial blocks
        blocked_frames = frames_in_file - block_remainder

        v_source = h5py.VirtualSource(
            filepath,
            name=dataset_name,
            shape=(frames_in_file, frame_shape[0], frame_shape[1]),
            dtype=dtype,
        )

        start = file_idx * frames_per_block
        stride = n_files * frames_per_block
        n_blocks = blocked_frames // frames_per_block

        if n_blocks:
            source = v_source[:blocked_frames, :, :]
            v_layout[
                h5py.MultiBlockSlice(
                    start=start, stride=stride, count=n_blocks, block=frames_per_block
                ),
                :,
                :,
            ] = source

        if block_remainder:
            # Last few frames that don't fit into a block
            source = v_source[blocked_frames:frames_in_file, :, :]
            v_layout[frame_count - block_remainder : frame_count, :, :] = source

    with h5py.File(path, "w", libver="latest") as f:
        f.create_virtual_dataset(dataset_name, v_layout, fillvalue=0)


def get_frame(n, shape=(10, 10)):
    return np.full(shape, n)


def get_round_robin_arrays(
    frames: int, block_size: int, n_files: int
) -> list[np.ndarray]:
    arrays = [[] for _ in range(n_files)]
    frame = 0
    while frame < frames:
        data_array = arrays[frame // block_size % n_files]
        for _ in range(block_size):
            data_array.append(get_frame(frame))
            frame += 1
            if frame == frames:
                break
    return [np.array(array) for array in arrays]


def simulate_round_robin(path: str, frames: int, block_size: int, n_files: int):
    file_name_prefix = Path(path).with_suffix("")
    filepaths = [f"{file_name_prefix}_{str(i + 1).zfill(6)}.h5" for i in range(n_files)]
    arrays = get_round_robin_arrays(frames, block_size, n_files)
    for filepath, data_array in zip(filepaths, arrays, strict=True):
        with h5py.File(filepath, "w") as f:
            f.create_dataset("data", data=data_array)


path = "test.h5"
frames = 105
block_size = 10
n_files = 4
blocks_per_file = 3

simulate_round_robin(path, frames, block_size, n_files)
create_interleave_vds(path, frames, block_size, blocks_per_file, (10, 10))
