"""FFmpeg sequencing (end-to-end concat) for compatible MP4 clips."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .transitions import uses_stream_copy


def require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError(
            "FFmpeg is not available on PATH. Install FFmpeg to sequence video clips."
        )
    return ffmpeg


def require_ffprobe() -> str:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise RuntimeError(
            "FFprobe is not available on PATH. Install FFmpeg to sequence video clips with fades."
        )
    return ffprobe


def _escape_concat_path(path: str) -> str:
    return path.replace("'", "'\\''")


def probe_has_audio(path: str, *, timeout: int = 30) -> bool:
    ffprobe = require_ffprobe()
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def probe_video_params(path: str, *, timeout: int = 30) -> tuple[int, int, str]:
    """Return (width, height, avg_frame_rate) of the first video stream."""
    ffprobe = require_ffprobe()
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate",
            "-of",
            "csv=p=0",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Cannot read video parameters for {path!r}")
    width, height, frame_rate = result.stdout.strip().split(",")[:3]
    return int(width), int(height), frame_rate


def _clips_uniform(segment_paths: list[str]) -> bool:
    """True when every clip shares the first clip's size and frame rate."""
    params = [probe_video_params(path) for path in segment_paths]
    return all(p == params[0] for p in params[1:])


def probe_duration(path: str, *, timeout: int = 30) -> float:
    ffprobe = require_ffprobe()
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Cannot read duration for {path!r}")
    return float(result.stdout.strip())


def sequence_videos_cut(segment_paths: list[str], output_path: str, *, timeout: int = 300) -> str:
    """Concatenate MP4 segments with the FFmpeg concat demuxer (cut-only, stream copy)."""
    if not segment_paths:
        raise ValueError("At least one video path is required")

    if len(segment_paths) == 1:
        return segment_paths[0]

    ffmpeg = require_ffmpeg()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    concat_path = out.with_suffix(out.suffix + ".concat.txt")

    try:
        with open(concat_path, "w", encoding="utf-8") as f:
            for path in segment_paths:
                f.write(f"file '{_escape_concat_path(path)}'\n")

        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(out),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg concat failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
            )
    finally:
        concat_path.unlink(missing_ok=True)

    return str(out)


def sequence_videos_fade(
    segment_paths: list[str],
    transitions: list[dict],
    output_path: str,
    *,
    timeout: int = 600,
) -> str:
    """Join clips with FFmpeg xfade / acrossfade (re-encodes to H.264 + AAC)."""
    if not segment_paths:
        raise ValueError("At least one video path is required")

    if len(segment_paths) == 1:
        return segment_paths[0]

    gap_count = len(segment_paths) - 1
    if len(transitions) != gap_count:
        raise ValueError(
            f"Expected {gap_count} transition(s) for {len(segment_paths)} segments, "
            f"got {len(transitions)}"
        )

    ffmpeg = require_ffmpeg()
    durations = [probe_duration(path) for path in segment_paths]
    # Audio crossfade only works when every segment has an audio stream;
    # otherwise produce a video-only output instead of failing in FFmpeg.
    with_audio = all(probe_has_audio(path) for path in segment_paths)

    # Conform every clip to the first clip's size and frame rate (scale +
    # letterbox), like dropping clips into an editing timeline. xfade and
    # concat require identical geometry across inputs.
    width, height, frame_rate = probe_video_params(segment_paths[0])

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [ffmpeg, "-y"]
    for path in segment_paths:
        cmd += ["-i", path]

    video_filters: list[str] = []
    audio_filters: list[str] = []

    for index in range(len(segment_paths)):
        video_filters.append(
            f"[{index}:v]"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1,fps={frame_rate}"
            f"[cv{index:02d}]"
        )
        if with_audio:
            audio_filters.append(
                f"[{index}:a]"
                "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"
                f"[ca{index:02d}]"
            )

    v_label = "cv00"
    a_label = "ca00"
    cumulative = durations[0]

    for index, transition in enumerate(transitions):
        if transition["type"] == "cut":
            trans_dur = float(transition["duration"])
        else:
            trans_dur = max(0.1, float(transition["duration"]))

        xfade_name = transition.get("xfade", "fade")
        offset = max(0.0, cumulative - trans_dur)
        next_idx = index + 1
        v_out = f"v{next_idx:02d}"
        a_out = f"a{next_idx:02d}"

        video_filters.append(
            f"[{v_label}][cv{next_idx:02d}]"
            f"xfade=transition={xfade_name}:duration={trans_dur:.3f}:offset={offset:.3f}"
            f"[{v_out}]"
        )
        if with_audio:
            audio_filters.append(
                f"[{a_label}][ca{next_idx:02d}]acrossfade=d={trans_dur:.3f}[{a_out}]"
            )

        v_label = v_out
        a_label = a_out
        cumulative += durations[next_idx] - trans_dur

    filter_complex = ";".join(video_filters + audio_filters)
    cmd += [
        "-filter_complex",
        filter_complex,
        "-map",
        f"[{v_label}]",
    ]
    if with_audio:
        cmd += ["-map", f"[{a_label}]", "-c:a", "aac", "-ar", "44100"]
    cmd += [
        "-c:v",
        "libx264",
        # 4:2:0 + faststart for broad player compatibility (Windows, web, mobile);
        # without this libx264 can emit High 4:4:4, which many decoders reject
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-crf",
        "18",
        "-preset",
        "fast",
        str(out),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg crossfade failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )

    return str(out)


def sequence_videos(
    segment_paths: list[str],
    output_path: str,
    *,
    join_mode: str,
    transitions: list[dict],
    timeout: int = 600,
) -> str:
    """Dispatch to stream-copy or crossfade sequencing."""
    if join_mode not in ("stream_copy", "fade"):
        raise ValueError(f"Unknown join_mode: {join_mode!r}")

    all_cuts = join_mode == "stream_copy" or uses_stream_copy(transitions)
    if all_cuts and len(segment_paths) > 1 and not _clips_uniform(segment_paths):
        # Mismatched size/frame rate: the concat demuxer would corrupt the
        # output, so conform + re-encode via the xfade path (cut transitions
        # there are 0.04 s, visually a hard cut).
        all_cuts = False

    if all_cuts:
        return sequence_videos_cut(segment_paths, output_path, timeout=min(timeout, 300))
    return sequence_videos_fade(segment_paths, transitions, output_path, timeout=timeout)
