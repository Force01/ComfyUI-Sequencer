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

- Full end-to-end workflow execution in ComfyUI should be validated manually after install
- Comfy Registry validation not yet completed
- Example workflow JSON may be added after beta if not included in this release

## Install

Clone or copy into `ComfyUI/custom_nodes/ComfyUI-Sequencer/` and restart ComfyUI.

```bash
git clone https://github.com/fundy/ComfyUI-Sequencer.git ComfyUI/custom_nodes/ComfyUI-Sequencer
```
