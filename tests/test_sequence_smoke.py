"""FFmpeg sequencing smoke tests (skipped when FFmpeg is unavailable)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from comfyui_sequencer.lib.sequence import (
    probe_has_audio,
    sequence_videos,
    sequence_videos_cut,
)
from comfyui_sequencer.lib.transitions import build_transitions

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(
    FFMPEG is None or FFPROBE is None,
    reason="FFmpeg/FFprobe not available on PATH",
)


def _make_clip(
    path: Path,
    *,
    width: int = 320,
    height: int = 240,
    fps: int = 24,
    duration: float = 1.0,
    with_audio: bool = False,
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={width}x{height}:r={fps}:d={duration}",
    ]
    if with_audio:
        cmd += [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-c:a",
            "aac",
        ]
    else:
        cmd += ["-an"]
    cmd += [
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-t",
        str(duration),
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])
    return str(path)


def test_sequence_cut_same_size_clips(tmp_path):
    clip_a = _make_clip(tmp_path / "a.mp4")
    clip_b = _make_clip(tmp_path / "b.mp4")
    out = tmp_path / "joined.mp4"

    result = sequence_videos_cut([clip_a, clip_b], str(out))
    assert Path(result).is_file()
    assert Path(result).stat().st_size > 0


def test_transition_falls_back_when_clips_differ(tmp_path):
    clip_a = _make_clip(tmp_path / "a.mp4", width=320, height=240)
    clip_b = _make_clip(tmp_path / "b.mp4", width=640, height=480)
    out = tmp_path / "joined.mp4"
    transitions = build_transitions(1, "cut", 0.5)

    result = sequence_videos(
        [clip_a, clip_b],
        str(out),
        join_mode="stream_copy",
        transitions=transitions,
    )
    assert Path(result).is_file()
    assert Path(result).stat().st_size > 0


def test_mixed_audio_does_not_fail(tmp_path):
    silent = _make_clip(tmp_path / "silent.mp4", with_audio=False)
    audible = _make_clip(tmp_path / "audible.mp4", with_audio=True)
    out = tmp_path / "joined.mp4"
    transitions = build_transitions(1, "dissolve", 0.25)

    result = sequence_videos(
        [silent, audible],
        str(out),
        join_mode="fade",
        transitions=transitions,
    )
    assert Path(result).is_file()
    assert probe_has_audio(result)
