"""Resolve MP4 paths from ComfyUI folders, absolute paths, or VIDEO sockets."""

from __future__ import annotations

import os
import re
from io import BytesIO

import folder_paths


def _assert_mp4_extension(line: str) -> None:
    name = line.replace("\\", "/").rstrip("/").split("/")[-1]
    if not name.lower().endswith(".mp4"):
        raise ValueError(f"Only MP4 files are supported: {line}")


def resolve_video_path(raw: str) -> str:
    line = raw.strip()
    if not line:
        raise ValueError("Empty video path")

    _assert_mp4_extension(line)

    resolved: str | None = None

    if folder_paths.exists_annotated_filepath(line):
        resolved = os.path.abspath(folder_paths.get_annotated_filepath(line))
    elif os.path.isfile(line):
        resolved = os.path.abspath(line)
    else:
        for base in (
            folder_paths.get_output_directory(),
            folder_paths.get_input_directory(),
        ):
            candidate = os.path.join(base, line)
            if os.path.isfile(candidate):
                resolved = os.path.abspath(candidate)
                break

    if resolved is None:
        raise FileNotFoundError(f"Video file not found: {line}")

    return resolved


def video_to_path(video) -> str:
    """Return an on-disk MP4 path from a ComfyUI VIDEO input."""
    source = video.get_stream_source()
    if isinstance(source, BytesIO):
        raise ValueError(
            "Video Sequencer requires MP4 files on disk. Wire Load Video nodes (not in-memory tensors)."
        )
    if not isinstance(source, str):
        raise ValueError("Unsupported video source for sequencing.")

    path = os.path.abspath(source)
    _assert_mp4_extension(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Video file not found: {path}")
    return path


def segment_index(name: str) -> int:
    match = re.search(r"(\d+)$", name)
    if not match:
        return 0
    return int(match.group(1))


def ordered_segment_paths(segments: dict) -> list[str]:
    connected = [(key, value) for key, value in segments.items() if value is not None]
    if not connected:
        raise ValueError(
            "Connect Load Video outputs to segment0, segment1, … in playback order."
        )
    connected.sort(key=lambda item: segment_index(item[0]))
    return [video_to_path(value) for _, value in connected]
