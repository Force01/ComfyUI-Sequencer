"""Path resolution and segment ordering tests."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from comfyui_sequencer.lib.paths import ordered_segment_paths, segment_index


def test_segment_index_zero_padded_names():
    assert segment_index("segment00") == 0
    assert segment_index("segment01") == 1
    assert segment_index("segment19") == 19


def test_ordered_segment_paths_sorts_by_index(tmp_path):
    paths = []
    for index in (2, 0, 1):
        clip = tmp_path / f"clip_{index}.mp4"
        clip.write_bytes(b"")
        paths.append(str(clip))

    segments = {
        "segment02": _video_from_file(paths[0]),
        "segment00": _video_from_file(paths[1]),
        "segment01": _video_from_file(paths[2]),
        "segment03": None,
    }

    resolved = ordered_segment_paths(segments)
    assert resolved == [paths[1], paths[2], paths[0]]


def test_ordered_segment_paths_requires_connection():
    with pytest.raises(ValueError, match="Connect VIDEO"):
        ordered_segment_paths({})


def _video_from_file(path: str):
    video = MagicMock()
    video.get_stream_source.return_value = os.path.abspath(path)
    return video
