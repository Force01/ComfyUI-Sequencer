# ComfyUI-Sequencer

**Video Sequencer** joins video clips end-to-end into one continuous video —
**instantly, losslessly, and with zero VRAM** in cut mode. Clips come from
loaded MP4 files or straight from video models earlier in the same workflow;
clips never need to fit in memory.

Connect clips in playback order — a new segment slot appears each time you
connect one (up to 20). Pick a transition for the junctions and queue the
workflow. Find it under **video/edit**.

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

Restart ComfyUI. The node appears under **video/edit** as **Video Sequencer**.

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

## Spill Clip to Disk

For long workflows that generate many clips in sequence, holding all of them
in memory simultaneously can exhaust RAM before the sequencer runs.

**Spill Clip to Disk** solves this. Place it between each clip generator and
the sequencer:

```text
Video Model ──► CreateVideo ──► Spill Clip to Disk ──► segment0 ──┐
Video Model ──► CreateVideo ──► Spill Clip to Disk ──► segment1 ──┴──► Video Sequencer
```

Each clip is immediately encoded to a temp H.264 MP4 and the in-memory tensors
are released, so only one clip's worth of data is in RAM at a time. The
sequencer then reads the clips back from disk when it runs.

**The temp files are not saved to your output folder.** They live in ComfyUI's
temp directory and are cleared with normal temp cleanup — they are not meant as
a permanent archive of individual clips.

If you want to keep the individual clips as named files, use **Save Video**
instead. Spill Clip to Disk is a memory pressure valve, not a save node.

## Mixed resolutions and frame rates

Clips are conformed to the **first clip's** size and frame rate, like dropping
clips into an editing timeline — smaller or differently-shaped clips are scaled
and letterboxed. When clips already match (and **cut** is selected), the
sequencer stream-copies instead: instant and lossless.

## Limitations

- **cut** mode is lossless only when all clips are file-backed MP4s sharing
  size, frame rate, and codec settings; otherwise the sequence is conformed
  and re-encoded automatically.
- Transitions re-encode; output duration shrinks by the overlap of each crossfade.
- When some clips have audio and others don't, silence is laid under the
  silent clips (video-only output only when no clip has audio).

## Support scope

This node does not know or care what produced the MP4 files. It only joins
compatible MP4 clips in the order you wire them.
