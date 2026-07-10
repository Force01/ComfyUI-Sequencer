"""Smart render tests (skipped when FFmpeg is unavailable)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from comfyui_sequencer.lib.sequence import probe_duration, probe_has_audio, sequence_videos
from comfyui_sequencer.lib.smart import SmartRenderUnavailable, sequence_videos_smart
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
    duration: float = 6.0,
    gop: int = 24,
    with_audio: bool = True,
    freq: int = 440,
) -> str:
    """720p/24fps test clip with a keyframe every `gop` frames."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=24:duration={duration}",
    ]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}", "-c:a", "aac"]
    else:
        cmd += ["-an"]
    cmd += [
        "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-g", str(gop), "-t", str(duration), str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])
    return str(path)


def test_smart_render_two_clips(tmp_path):
    a = _make_clip(tmp_path / "a.mp4")
    b = _make_clip(tmp_path / "b.mp4", freq=660)
    out = tmp_path / "joined.mp4"
    transitions = build_transitions(1, "dissolve", 0.5)

    result = sequence_videos_smart([a, b], transitions, str(out))
    assert Path(result).is_file()
    # 6 + 6 - 0.5 overlap
    assert probe_duration(result) == pytest.approx(11.5, abs=0.25)
    assert probe_has_audio(result)


def test_smart_render_three_clip_chain(tmp_path):
    clips = [
        _make_clip(tmp_path / f"c{i}.mp4", freq=440 + 110 * i) for i in range(3)
    ]
    out = tmp_path / "joined.mp4"
    transitions = build_transitions(2, "dissolve", 0.5)

    result = sequence_videos_smart(clips, transitions, str(out))
    assert probe_duration(result) == pytest.approx(17.0, abs=0.35)


def test_smart_render_untouched_frames_are_lossless(tmp_path):
    a = _make_clip(tmp_path / "a.mp4")
    b = _make_clip(tmp_path / "b.mp4", freq=660)
    out = tmp_path / "joined.mp4"
    transitions = build_transitions(1, "dissolve", 0.5)
    result = sequence_videos_smart([a, b], transitions, str(out))

    def hashes(path, seconds):
        r = subprocess.run(
            [FFMPEG, "-v", "error", "-t", str(seconds), "-i", path,
             "-map", "0:v", "-f", "framemd5", "-"],
            capture_output=True, text=True,
        )
        return [line.rsplit(",", 1)[-1].strip() for line in r.stdout.splitlines()
                if line and not line.startswith("#")]

    # The first seconds of the output are stream-copied from clip A: the
    # frame hashes must be bit-identical to the source.
    assert hashes(result, 3) == hashes(a, 3)


def test_smart_render_rejects_sparse_keyframes(tmp_path):
    # A single keyframe at t=0 leaves nowhere for the incoming clip's
    # lossless part to start: smart render must refuse, not corrupt.
    a = _make_clip(tmp_path / "a.mp4", gop=9999)
    b = _make_clip(tmp_path / "b.mp4", gop=9999, freq=660)
    transitions = build_transitions(1, "dissolve", 0.5)

    with pytest.raises(SmartRenderUnavailable):
        sequence_videos_smart([a, b], transitions, str(tmp_path / "joined.mp4"))


def test_dispatcher_falls_back_when_smart_unavailable(tmp_path):
    # Sparse keyframes through the public entry point: output must still be
    # produced via the full re-encode path.
    a = _make_clip(tmp_path / "a.mp4", gop=9999)
    b = _make_clip(tmp_path / "b.mp4", gop=9999, freq=660)
    out = tmp_path / "joined.mp4"
    transitions = build_transitions(1, "dissolve", 0.5)

    result = sequence_videos(
        [a, b], str(out), join_mode="fade", transitions=transitions
    )
    assert Path(result).is_file()
    assert probe_duration(result) == pytest.approx(11.5, abs=0.25)


def test_smart_render_video_only_clips(tmp_path):
    a = _make_clip(tmp_path / "a.mp4", with_audio=False)
    b = _make_clip(tmp_path / "b.mp4", with_audio=False)
    out = tmp_path / "joined.mp4"
    transitions = build_transitions(1, "dissolve", 0.5)

    result = sequence_videos_smart([a, b], transitions, str(out))
    assert Path(result).is_file()
    assert not probe_has_audio(result)
