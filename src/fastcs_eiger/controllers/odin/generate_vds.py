import math
from pathlib import Path

import h5py


def get_frames_per_file_writer(
    frame_count: int, frames_per_block: int, n_file_writers: int
) -> list[int]:
    frame_numbers_per_file = []
    n_blocks = math.ceil(frame_count / frames_per_block)
    min_blocks_per_file = n_blocks // n_file_writers
    remainder = n_blocks - min_blocks_per_file * n_file_writers
    for i in range(n_file_writers):
        blocks = min_blocks_per_file + (i < remainder)
        frame_numbers_per_file.append(blocks * frames_per_block)
    overflow = sum(frame_numbers_per_file) - frame_count
    frame_numbers_per_file[remainder - 1] -= overflow
    return frame_numbers_per_file


def create_interleave_vds(
    path: Path,
    prefix: str,
    frame_count: int,
    frames_per_block: int,
    blocks_per_file: int,
    frame_shape: tuple[int, int],
    dtype: str = "float",
    n_file_writers: int = 4,
) -> None:
    dataset_name = "data"
    max_frames_per_file = (
        frames_per_block * blocks_per_file if blocks_per_file else frame_count
    )

    frame_count_per_file_writer = get_frames_per_file_writer(
        frame_count, frames_per_block, n_file_writers
    )

    v_layout = h5py.VirtualLayout(
        shape=(frame_count, frame_shape[0], frame_shape[1]),
        dtype=dtype,
    )

    for file_writer_idx, n_frames in enumerate(frame_count_per_file_writer):
        n_files = math.ceil(n_frames / max_frames_per_file)

        for file_idx in range(n_files):
            frames_in_file = min(
                max_frames_per_file, n_frames - (max_frames_per_file * file_idx)
            )
            file_number = 1 + file_writer_idx + file_idx * n_file_writers

            v_source = h5py.VirtualSource(
                f"{path / prefix}_{str(file_number).zfill(6)}.h5",
                name=dataset_name,
                shape=(frames_in_file, frame_shape[0], frame_shape[1]),
                dtype=dtype,
            )

            # MultiBlockSlice cannot contain partial blocks
            remainder_frames = frames_in_file % frames_per_block
            full_block_frames = frames_in_file - remainder_frames

            start = (
                file_writer_idx * frames_per_block
                + max_frames_per_file * n_file_writers * file_idx
            )
            n_blocks = full_block_frames // frames_per_block

            if n_blocks:
                stride = n_file_writers * frames_per_block
                source = v_source[:full_block_frames, :, :]
                v_layout[
                    h5py.MultiBlockSlice(
                        start=start,
                        stride=stride,
                        count=n_blocks,
                        block=frames_per_block,
                    ),
                    :,
                    :,
                ] = source

            if remainder_frames:
                # Last few frames that don't fit into a block
                source = v_source[full_block_frames:frames_in_file, :, :]
                v_layout[frame_count - remainder_frames : frame_count, :, :] = source

    with h5py.File(f"{path / prefix}_vds.h5", "w", libver="latest") as f:
        f.create_virtual_dataset(dataset_name, v_layout)
