import math
from pathlib import Path

import h5py


def get_frames_per_file(
    frame_count: int, frames_per_block: int, n_files: int
) -> list[int]:
    frame_numbers_per_file = []
    n_blocks = math.ceil(frame_count / frames_per_block)
    min_blocks_per_file = n_blocks // n_files
    remainder = n_blocks - min_blocks_per_file * n_files
    for i in range(n_files):
        blocks = min_blocks_per_file + (i < remainder)
        frame_numbers_per_file.append(blocks * frames_per_block)
    overflow = sum(frame_numbers_per_file) - frame_count
    frame_numbers_per_file[remainder - 1] -= overflow
    return frame_numbers_per_file


def create_interleave_vds(
    path: str,
    frame_count: int,
    frames_per_block: int,
    blocks_per_file: int,
    frame_shape: tuple[int, int],
    dtype: str = "float",
) -> None:
    dataset_name = "data"
    frames_per_file = min(
        (frames_per_block * blocks_per_file if blocks_per_file else frame_count),
        frame_count,
    )
    n_files = math.ceil(frame_count / frames_per_file)
    file_name_prefix = Path(path).with_suffix("")
    filepaths = [f"{file_name_prefix}_{str(i + 1).zfill(6)}.h5" for i in range(n_files)]
    frame_count_per_file = get_frames_per_file(frame_count, frames_per_block, n_files)

    v_layout = h5py.VirtualLayout(
        shape=(frame_count, frame_shape[0], frame_shape[1]),
        dtype=dtype,
    )

    for file_idx, (filepath, frames_in_file) in enumerate(
        zip(filepaths, frame_count_per_file, strict=True)
    ):
        v_source = h5py.VirtualSource(
            filepath,
            name=dataset_name,
            shape=(frames_in_file, frame_shape[0], frame_shape[1]),
            dtype=dtype,
        )

        # MultiBlockSlice cannot contain partial blocks
        block_remainder = frames_in_file % frames_per_block
        blocked_frames = frames_in_file - block_remainder

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
        f.create_virtual_dataset(dataset_name, v_layout)
