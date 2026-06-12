"""Resolve MP4 paths from ComfyUI folders, absolute paths, or VIDEO sockets."""

from __future__ import annotations

import os
import re
import uuid

import folder_paths
from comfy_api.latest import VideoCodec, VideoContainer


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


def _materialize_video(video) -> str:
    """Write an in-memory or non-MP4 VIDEO input to a temp H.264 MP4."""
    temp_dir = folder_paths.get_temp_directory()
    os.makedirs(temp_dir, exist_ok=True)
    path = os.path.join(temp_dir, f"sequencer_{uuid.uuid4().hex}.mp4")
    video.save_to(path, format=VideoContainer.MP4, codec=VideoCodec.H264)
    return path


def video_to_path(video) -> str:
    """Return an on-disk MP4 path for a ComfyUI VIDEO input.

    File-backed MP4s are used in place. Anything else — video generated
    in-memory upstream in the workflow, or a non-MP4 file — is encoded once
    to a temp MP4.
    """
    source = video.get_stream_source()
    if isinstance(source, str):
        path = os.path.abspath(source)
        name = path.replace("\\", "/").rstrip("/").split("/")[-1]
        if name.lower().endswith(".mp4"):
            if not os.path.isfile(path):
                raise FileNotFoundError(f"Video file not found: {path}")
            return path

    return _materialize_video(video)


def segment_index(name: str) -> int:
    match = re.search(r"(\d+)$", name)
    if not match:
        return 0
    return int(match.group(1))


def ordered_segment_paths(segments: dict) -> list[str]:
    connected = [(key, value) for key, value in segments.items() if value is not None]
    if not connected:
        raise ValueError(
            "Connect VIDEO outputs to segment0, segment1, … in playback order."
        )
    connected.sort(key=lambda item: segment_index(item[0]))
    return [video_to_path(value) for _, value in connected]
