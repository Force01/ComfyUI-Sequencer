# v0.1.0-beta

Initial public beta of **ComfyUI-Sequencer**.

## Includes

- FFmpeg-based video sequencing
- Hard cuts (stream-copy when clips match)
- Transition support (dissolve, fades, wipes, slides, and more)
- Mixed audio / silent clip handling
- Spill-to-disk utility node (`SpillClipToDisk`)
- ComfyUI V3 node registration (`VideoSequencer`, `SpillClipToDisk`)
- No CUDA requirement
- No model-loader or GGUF side effects

## Requirements

- ComfyUI 0.24+
- FFmpeg and FFprobe on `PATH`

## Known limitations

- Comfy Registry validation not yet completed
- Example workflow JSON may be added after beta if not included in this release

## Manual validation

Full end-to-end workflow execution has been validated in a live ComfyUI instance (2026-07-08):

- Load Video -> Video Sequencer (`dissolve`) -> Save Video
- Load Video -> Video Sequencer (`cut`) -> Save Video
- Chained sequencers: Video Sequencer -> Spill Clip to Disk -> Video Sequencer -> Save Video, mixing loaded clips and a prior sequencer's output

That chained-sequencer testing surfaced and fixed two real bugs:

- `cut` mode's compatibility check only compared resolution, frame rate, and audio presence, so clips with matching geometry but different codec profile could pass as "compatible" and produce a corrupted stream-copy (correct duration/audio, frozen video). The check now also compares codec, profile, and pixel format.
- The crossfade (`xfade`) path could emit non-monotonic timestamps for the tail of the second clip whenever the first clip was longer, which some muxers silently dropped — truncating the output right after the transition. Fixed by re-stamping to a constant frame rate immediately after each `xfade`.

## Install

Clone or copy into `ComfyUI/custom_nodes/ComfyUI-Sequencer/` and restart ComfyUI.

```bash
git clone https://github.com/Force01/ComfyUI-Sequencer.git ComfyUI/custom_nodes/ComfyUI-Sequencer
```
