# ComfyUI-Sequencer

Video Sequencer joins video clips end-to-end into one continuous video inside ComfyUI. It can join loaded MP4 files or clips generated earlier in the same workflow.

In `cut` mode, compatible file-backed clips are joined instantly and losslessly using FFmpeg stream copy. For generated clips or long workflows, use **Spill Clip to Disk** to write clips to temporary files before sequencing.

Connect clips in playback order. A new segment slot appears each time you connect one, up to 20 segments. Pick a transition, queue the workflow, and the sequencer outputs a single video.

Find it under:

```text
video/edit
```

---

## Features

- Join up to 20 video clips
- Hard cut mode with lossless FFmpeg stream copy when clips are compatible
- Transition modes with automatic re-encode
- Audio handling for clips with or without audio
- Automatic conforming for mixed resolutions and frame rates
- Accepts loaded videos or generated `VIDEO` outputs
- Optional spill-to-disk node for long workflows
- No GPU required for sequencing

---

## Transitions

The transition dropdown applies one transition style at every junction.

| Transition | Description |
|---|---|
| `cut` | Hard cut. Uses FFmpeg concat demuxer when clips are compatible. No re-encode. Fast and lossless. |
| `dissolve` | Classic crossfade between clips. |
| `fade to black` | Fade out through black, then fade in. |
| `fade to white` | Fade out through white, then fade in. |
| `wipe left` / `right` / `up` / `down` | The next clip wipes across the frame. |
| `slide left` / `right` / `up` / `down` | The next clip pushes the previous clip out. |
| `circle open` / `circle close` | Iris-style transition. |
| `pixelate` | Pixelated dissolve transition. |

Everything except `cut` re-encodes to H.264. Transition duration is controlled by the `transition_seconds` setting.

When every clip has audio, transition modes crossfade audio to AAC.

---

## Mixing transitions

To use different transitions between different clips, chain sequencers together.

Example: dissolve A → B, then hard cut to C.

```text
A ──► segment0 ─┐
B ──► segment1 ─┴─► Video Sequencer (dissolve) ──► segment0 ─┐
C ───────────────────────────────────────────────► segment1 ─┴─► Video Sequencer (cut) ──► video
```

The sequencer output is a `VIDEO`, so it can be wired into another sequencer.

---

## Requirements

- ComfyUI 0.24+
- FFmpeg and FFprobe available on PATH
- Python environment used by ComfyUI

No GPU is required for sequencing.

---

## Install

Clone or copy this repo into your ComfyUI `custom_nodes` directory:

```text
ComfyUI/custom_nodes/ComfyUI-Sequencer/
```

Restart ComfyUI.

The node appears under:

```text
video/edit
```

as:

```text
Video Sequencer
```

---

## Basic use

```text
Load Video (clip A) ──► segment0 ──┐
Load Video (clip B) ──► segment1 ──┼──► Video Sequencer ──► video
Load Video (clip C) ──► segment2 ──┘
```

Steps:

1. Add one `Load Video` node for each clip.
2. Add `Video Sequencer`.
3. Connect each clip in playback order.
4. Choose a transition mode.
5. Set `transition_seconds` if using transitions.
6. Queue the workflow.

The result is saved under ComfyUI's output folder using the selected `filename_prefix`.

---

## Generated video workflows

Segments accept any ComfyUI `VIDEO` output.

That means clips generated earlier in the same workflow can be wired directly into the sequencer.

```text
Video Model ──► CreateVideo ──► segment0 ──┐
Video Model ──► CreateVideo ──► segment1 ──┼──► Video Sequencer ──► video
Video Model ──► CreateVideo ──► segment2 ──┘
```

ComfyUI runs the sequencer after all connected clips have finished rendering.

Generated clips are encoded to temporary H.264 MP4 files before joining.

---

## Spill Clip to Disk

Long workflows can hold many generated clips in memory before the final sequencer node runs.

**Spill Clip to Disk** writes each clip to a temporary MP4 as soon as it is generated, then releases the in-memory clip data.

Use it between a clip generator and the sequencer:

```text
Video Model ──► CreateVideo ──► Spill Clip to Disk ──► segment0 ──┐
Video Model ──► CreateVideo ──► Spill Clip to Disk ──► segment1 ──┴──► Video Sequencer
```

This helps reduce RAM pressure in longer workflows.

The temporary files are stored in ComfyUI's temp directory. They are not permanent saved outputs.

To keep individual clips as named files, use `Save Video` instead.

---

## Mixed resolutions and frame rates

The sequencer conforms clips to the first clip's size and frame rate.

Differently sized clips are scaled and letterboxed, similar to dropping clips into an editing timeline.

When clips already match and `cut` mode is selected, the sequencer can stream-copy instead of re-encoding.

---

## Audio behavior

Audio is preserved when possible.

| Clip audio state | Result |
|---|---|
| All clips have audio | Audio is joined or crossfaded depending on transition mode |
| Some clips have audio | Silence is added under silent clips |
| No clips have audio | Output is video-only |

Transition modes output AAC audio when audio is present.

---

## Limitations

- `cut` mode is lossless only when clips are compatible for FFmpeg stream copy.
- If clips differ in size, frame rate, codec, or container settings, the sequence is conformed and re-encoded.
- Transitions require re-encoding.
- Transition output duration shrinks by the overlap amount.
- Spill Clip to Disk writes temporary files, not permanent clip exports.

---

## Development

Run checks:

```bash
python -m compileall .
python -m pytest -v
```

FFmpeg-based tests run when FFmpeg is available and skip gracefully when it is not.

---

## License

MIT
