# ComfyUI-Sequencer

**Video Sequencer** joins MP4 clips end-to-end into one continuous video.

Connect clips in playback order — a new segment slot appears each time you
connect one (up to 20). Pick how the clips join and queue the workflow.

## Join modes

- **cut** — hard cuts. FFmpeg concat demuxer, no re-encode — instant and
  lossless. Clips must share codec/container settings.
- **dissolve** — crossfade between clips, lasting **dissolve seconds**.
  Re-encodes to H.264 (audio crossfades to AAC when every clip has audio).

## Requirements

- ComfyUI 0.24+ (V3 custom node API)
- FFmpeg and FFprobe on `PATH`

## Install

Copy or clone this folder into your ComfyUI `custom_nodes` directory:

```text
custom_nodes/ComfyUI-Sequencer/
```

Restart ComfyUI. The node appears under **video** as **Video Sequencer**.

## Use

```text
Load Video (clip A) ──► segment0 ──┐
Load Video (clip B) ──► segment1 ──┼──► Video Sequencer ──► video
Load Video (clip C) ──► segment2 ──┘    (slots grow as you connect)
```

1. Add a **Load Video** node for each MP4 clip (from `output/` or `input/`).
2. Add **Video Sequencer** and connect each clip in playback order.
3. Set **join_mode** to `cut` or `dissolve` (and **dissolve seconds** for fade length).
4. Queue the workflow. The result saves under `output/` with **filename_prefix**
   and previews on the node.

## Limitations

- Inputs must be MP4 files on disk, loaded with **Load Video**.
- **cut** mode requires compatible codec/container settings across clips.
- **dissolve** re-encodes; output duration shrinks by the overlap of each crossfade.
- Clips without audio produce a video-only result in dissolve mode.

## Support scope

This node does not know or care what produced the MP4 files. It only joins
compatible MP4 clips in the order you wire them.
