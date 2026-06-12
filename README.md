# ComfyUI-Sequencer

**Video Sequencer** joins video clips end-to-end into one continuous video —
loaded MP4 files or clips generated earlier in the same workflow.

Connect clips in playback order — a new segment slot appears each time you
connect one (up to 20). Pick how the clips join and queue the workflow.

## Transitions

The **transition** dropdown applies one transition style at every junction:

- **cut** — hard cuts. FFmpeg concat demuxer, no re-encode — instant and
  lossless. Clips must share codec/container settings.
- **dissolve** — classic crossfade between clips.
- **fade to black** / **fade to white** — fade out through black/white, then in.
- **wipe left / right / up / down** — the next clip wipes across the frame.
- **slide left / right / up / down** — the next clip pushes the previous one out.
- **circle open** / **circle close** — iris in or out.
- **pixelate** — pixelated dissolve.

Everything except **cut** re-encodes to H.264 and lasts **transition seconds**
(audio crossfades to AAC when every clip has audio).

### Mixing transitions

Chain sequencers: the node's output is a VIDEO, so wire one sequencer's result
into another's `segment0`. Example — dissolve A→B, hard cut to C:

```text
A ──► segment0 ─┐
B ──► segment1 ─┴─► Sequencer (dissolve) ──► segment0 ─┐
C ─────────────────────────────────────────► segment1 ─┴─► Sequencer (cut) ──► video
```

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

## Pipelines

Segments accept any **VIDEO** output, not just **Load Video**. Clips generated
earlier in the same workflow (e.g. by a video model) can be wired straight into
the sequencer — ComfyUI runs the sequencer only after every connected clip has
finished rendering. In-memory clips are encoded once to a temp H.264 MP4 before
joining.

## Limitations

- **cut** mode is lossless only for file-backed MP4 clips with compatible
  codec/container settings; in-memory or non-MP4 clips are re-encoded to
  temp files first.
- **dissolve** re-encodes; output duration shrinks by the overlap of each crossfade.
- Clips without audio produce a video-only result in dissolve mode.

## Support scope

This node does not know or care what produced the MP4 files. It only joins
compatible MP4 clips in the order you wire them.
