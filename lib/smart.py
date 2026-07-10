"""Smart render: re-encode only the frames around each transition.

Stream-copies the untouched majority of every clip losslessly and re-encodes
only a small window around each junction (the "smart render" technique real
NLEs use). Falls back to the full re-encode path in sequence.py whenever a
precondition fails — the worst case is always today's behavior, never broken
output.

Preconditions (checked per run, any failure raises SmartRenderUnavailable):
- clips uniform (size, frame rate, codec, profile, pix_fmt, audio presence)
- codec is h264 with a profile we can reproduce, pix_fmt yuv420p
- every clip after the first has a keyframe shortly after the transition
  window (the lossless part must start on a keyframe to be decodable)
- every clip keeps a minimum lossless middle between its junction cuts

Prototype findings baked in:
- outpoint cuts by DTS, not PTS: compute the exact decode-order prefix that
  survives the cut and start the transition segment on the next frame
- transition segments are encoded with -bf 0 so their DTS never dips below
  the preceding lossless segment's at the splice
- AAC audio cannot be spliced losslessly, so the audio track is rebuilt in
  one continuous decode/encode pass over the originals (cheap) and muxed
  with the stream-copied video
"""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from .sequence import (
    probe_duration,
    probe_has_audio,
    probe_video_params,
    require_ffmpeg,
    require_ffprobe,
)

# Minimum lossless middle a clip must keep between junction cuts.
MIN_LOSSLESS_GAP = 0.5
# Extra tail of the outgoing clip included in the re-encoded segment, beyond
# the transition itself, so seek/cut rounding never lands inside the blend.
CUT_MARGIN = 0.25
# How far into the incoming clip to look for a usable keyframe before
# giving up (a segment longer than this beats little vs full re-encode).
KF_SEARCH_WINDOW = 30.0

_PROFILE_FLAGS = {
    "High": "high",
    "Main": "main",
    "Baseline": "baseline",
    "Constrained Baseline": "baseline",
}


class SmartRenderUnavailable(Exception):
    """Raised when a precondition fails; caller falls back to full re-encode."""


@dataclass
class _Junction:
    seg_start: float      # pts in the outgoing clip where the segment begins
    outpoint: float       # dts-based concat outpoint for the outgoing clip
    a_video_end: float    # outgoing clip's video end (last pts + frame dur)
    b_keyframe: float     # pts in the incoming clip where lossless resumes


def _probe_packets(path: str, interval: str | None, *, timeout: int = 60) -> list[dict]:
    """Return video packets as dicts with float pts/dts and key flag."""
    ffprobe = require_ffprobe()
    cmd = [ffprobe, "-v", "error", "-select_streams", "v:0"]
    if interval:
        cmd += ["-read_intervals", interval]
    cmd += ["-show_entries", "packet=pts_time,dts_time,flags", "-of", "json", path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise SmartRenderUnavailable(f"cannot probe packets for {path!r}")
    packets = []
    for p in json.loads(result.stdout).get("packets", []):
        try:
            packets.append({
                "pts": float(p["pts_time"]),
                "dts": float(p["dts_time"]),
                "key": p.get("flags", "").startswith("K"),
            })
        except (KeyError, ValueError):
            # VFR or missing timestamps: the cut arithmetic below is unsafe.
            raise SmartRenderUnavailable(f"unusable packet timestamps in {path!r}")
    if not packets:
        raise SmartRenderUnavailable(f"no video packets probed in {path!r}")
    return packets


def _plan_junction(a_path: str, b_path: str, trans_dur: float, frame_dur: float,
                   a_lossless_start: float) -> _Junction:
    """Compute exact cut points for one junction (clip A -> clip B)."""
    a_dur = probe_duration(a_path)
    cut_target = a_dur - trans_dur - CUT_MARGIN
    if cut_target <= a_lossless_start + MIN_LOSSLESS_GAP:
        raise SmartRenderUnavailable(
            f"clip {a_path!r} too short for a lossless middle"
        )

    # Probe the tail of A. outpoint cuts by DTS (decode order), so find the
    # decode-order prefix whose frames all have pts < cut_target, then start
    # the segment exactly one frame after the last surviving pts.
    tail = _probe_packets(a_path, f"{max(0.0, cut_target - 10):.3f}%")
    tail.sort(key=lambda p: p["dts"])
    running_max = 0.0
    keep = 0
    for i, p in enumerate(tail):
        if max(running_max, p["pts"]) + frame_dur / 2 > cut_target:
            break
        running_max = max(running_max, p["pts"])
        keep = i + 1
    if keep == 0 or keep >= len(tail):
        raise SmartRenderUnavailable(f"no usable cut point in {a_path!r}")
    outpoint = (tail[keep - 1]["dts"] + tail[keep]["dts"]) / 2
    seg_start = running_max + frame_dur
    a_video_end = max(p["pts"] for p in tail) + frame_dur

    # The incoming clip's lossless part must start on a keyframe placed
    # after the transition window.
    head = _probe_packets(b_path, f"0%+{KF_SEARCH_WINDOW:.0f}")
    b_keyframe = None
    for p in head:
        if p["key"] and p["pts"] >= trans_dur + CUT_MARGIN:
            b_keyframe = p["pts"]
            break
    if b_keyframe is None:
        raise SmartRenderUnavailable(
            f"no keyframe within {KF_SEARCH_WINDOW:.0f}s after the transition "
            f"window in {b_path!r}"
        )

    return _Junction(seg_start=seg_start, outpoint=outpoint,
                     a_video_end=a_video_end, b_keyframe=b_keyframe)


def _encode_segment(a_path: str, b_path: str, junction: _Junction,
                    transition: dict, frame_rate: str, profile_flag: str,
                    out_path: str, *, timeout: int) -> None:
    """Re-encode just the overlap window around one junction (video only)."""
    ffmpeg = require_ffmpeg()
    trans_dur = max(0.04, float(transition["duration"]))
    xfade = transition.get("xfade", "fade")
    offset = (junction.a_video_end - junction.seg_start) - trans_dur
    filter_complex = (
        f"[0:v]setsar=1,fps={frame_rate}[va];"
        f"[1:v]setsar=1,fps={frame_rate}[vb];"
        f"[va][vb]xfade=transition={xfade}:duration={trans_dur:.3f}:offset={offset:.3f},"
        # Segments splice against stream-copied footage: re-stamp to strict
        # CFR and encode without B-frames so DTS never dips below the
        # preceding lossless segment at the joint.
        f"setpts=N/({frame_rate}*TB),fps={frame_rate}[v]"
    )
    cmd = [
        ffmpeg, "-y",
        "-ss", f"{junction.seg_start:.6f}", "-i", a_path,
        "-t", f"{junction.b_keyframe:.6f}", "-i", b_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-an",
        "-c:v", "libx264", "-profile:v", profile_flag,
        "-pix_fmt", "yuv420p", "-bf", "0",
        "-crf", "18", "-preset", "fast",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise SmartRenderUnavailable(
            f"segment encode failed (exit {result.returncode}):\n{result.stderr[-1000:]}"
        )


def _build_audio(segment_paths: list[str], transitions: list[dict],
                 out_path: str, *, timeout: int) -> None:
    """Rebuild the full audio track: originals decoded once, crossfaded at
    each junction, encoded once. Sample-exact continuity, negligible cost."""
    ffmpeg = require_ffmpeg()
    cmd = [ffmpeg, "-y"]
    for path in segment_paths:
        cmd += ["-i", path]
    filters = []
    for i in range(len(segment_paths)):
        filters.append(
            f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[ca{i:02d}]"
        )
    label = "ca00"
    for i, transition in enumerate(transitions):
        trans_dur = max(0.04, float(transition["duration"]))
        nxt = f"a{i + 1:02d}"
        filters.append(f"[{label}][ca{i + 1:02d}]acrossfade=d={trans_dur:.3f}[{nxt}]")
        label = nxt
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", f"[{label}]", "-c:a", "aac", "-ar", "44100",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise SmartRenderUnavailable(
            f"audio build failed (exit {result.returncode}):\n{result.stderr[-1000:]}"
        )


def _concat_escape(path: str) -> str:
    return path.replace("\\", "/").replace("'", "'\\''")


def sequence_videos_smart(segment_paths: list[str], transitions: list[dict],
                          output_path: str, *, timeout: int = 600) -> str:
    """Join clips re-encoding only the overlap window around each junction.

    Raises SmartRenderUnavailable when any precondition fails; the caller
    falls back to the full re-encode path.
    """
    if len(segment_paths) < 2:
        raise SmartRenderUnavailable("smart render needs at least two clips")
    if len(transitions) != len(segment_paths) - 1:
        raise SmartRenderUnavailable("transition count mismatch")

    width, height, frame_rate, codec, profile, pix_fmt = probe_video_params(segment_paths[0])
    if codec != "h264" or pix_fmt != "yuv420p":
        raise SmartRenderUnavailable(f"unsupported codec/pix_fmt: {codec}/{pix_fmt}")
    profile_flag = _PROFILE_FLAGS.get(profile)
    if profile_flag is None:
        raise SmartRenderUnavailable(f"unsupported h264 profile: {profile!r}")
    try:
        frame_dur = 1.0 / float(Fraction(frame_rate))
    except (ValueError, ZeroDivisionError):
        raise SmartRenderUnavailable(f"unusable frame rate: {frame_rate!r}")

    with_audio = probe_has_audio(segment_paths[0])

    # Plan every junction up front so any failure falls back before any
    # encoding work happens.
    junctions: list[_Junction] = []
    lossless_start = 0.0
    for i, transition in enumerate(transitions):
        trans_dur = max(0.04, float(transition["duration"]))
        junction = _plan_junction(
            segment_paths[i], segment_paths[i + 1], trans_dur, frame_dur,
            lossless_start,
        )
        junctions.append(junction)
        lossless_start = junction.b_keyframe
    # The final clip's lossless part must also be non-degenerate.
    if probe_duration(segment_paths[-1]) <= lossless_start + MIN_LOSSLESS_GAP:
        raise SmartRenderUnavailable("final clip too short after its junction cut")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.parent / f".smart_{uuid.uuid4().hex}"
    work.mkdir()

    try:
        seg_files = []
        for i, junction in enumerate(junctions):
            seg_path = str(work / f"seg{i:02d}.mp4")
            _encode_segment(
                segment_paths[i], segment_paths[i + 1], junction,
                transitions[i], frame_rate, profile_flag, seg_path,
                timeout=timeout,
            )
            seg_files.append(seg_path)

        concat_path = work / "concat.txt"
        with open(concat_path, "w", encoding="utf-8") as f:
            for i, path in enumerate(segment_paths):
                f.write(f"file '{_concat_escape(path)}'\n")
                if i > 0:
                    f.write(f"inpoint {junctions[i - 1].b_keyframe:.6f}\n")
                if i < len(junctions):
                    f.write(f"outpoint {junctions[i].outpoint:.6f}\n")
                    f.write(f"file '{_concat_escape(seg_files[i])}'\n")

        ffmpeg = require_ffmpeg()
        if with_audio:
            audio_path = str(work / "audio.m4a")
            _build_audio(segment_paths, transitions, audio_path, timeout=timeout)
            # Single pass: stream-copy the concatenated video and the rebuilt
            # audio straight into the final file — the big video data is
            # written exactly once.
            final_cmd = [ffmpeg, "-y",
                         "-f", "concat", "-safe", "0", "-i", str(concat_path),
                         "-i", audio_path,
                         "-map", "0:v", "-map", "1:a", "-c", "copy",
                         "-movflags", "+faststart", str(out)]
        else:
            final_cmd = [ffmpeg, "-y",
                         "-f", "concat", "-safe", "0", "-i", str(concat_path),
                         "-map", "0:v", "-c", "copy",
                         "-movflags", "+faststart", str(out)]
        result = subprocess.run(final_cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise SmartRenderUnavailable(
                f"final concat/mux failed (exit {result.returncode}):\n{result.stderr[-1000:]}"
            )
    finally:
        for child in work.glob("*"):
            child.unlink(missing_ok=True)
        work.rmdir()

    return str(out)
