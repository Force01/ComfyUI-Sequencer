"""SpillClipToDisk — write a generated clip to disk immediately.

ComfyUI's CreateVideo returns a VideoFromComponents that retains full decoded
image tensors (~1.86 GiB per 121-frame 1536×896 clip) until the object is
garbage-collected. When many clips feed a VideoSequencer, all of them stay
alive simultaneously because the sequencer hasn't executed yet.

Place this node between every CreateVideo and VideoSequencer. It calls
video.save_to() the moment the clip is ready, returns a VideoFromFile backed
by the temp MP4, and lets the upstream tensor become eligible for GC — keeping
per-clip RAM roughly constant regardless of how many clips are in the sequence.
"""

from __future__ import annotations

import gc
import os
import uuid

import torch
import folder_paths
from comfy_api.latest import InputImpl, VideoCodec, VideoContainer, io


class SpillClipToDisk(io.ComfyNode):
    """Write an in-memory video clip to a temp MP4 and return a file-backed reference."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Sequencer_SpillClipToDisk",
            display_name="Spill Clip to Disk",
            category="video/memory",
            description=(
                "Write a generated video clip to a temporary MP4 on disk the moment "
                "it is ready, then return a file-backed VIDEO reference. The upstream "
                "image/audio tensors are released after the write completes, keeping "
                "system RAM roughly constant when many clips feed a VideoSequencer."
            ),
            search_aliases=["offload", "temp", "spill", "save clip", "memory", "ram"],
            inputs=[
                io.Video.Input("video", tooltip="In-memory clip from CreateVideo."),
            ],
            outputs=[
                io.Video.Output(display_name="video"),
            ],
        )

    @classmethod
    def execute(cls, video) -> io.NodeOutput:
        temp_dir = folder_paths.get_temp_directory()
        os.makedirs(temp_dir, exist_ok=True)
        path = os.path.join(temp_dir, f"spill_{uuid.uuid4().hex}.mp4")
        video.save_to(path, format=VideoContainer.MP4, codec=VideoCodec.H264)
        del video
        _release_clip_memory()
        return io.NodeOutput(InputImpl.VideoFromFile(path))


def _release_clip_memory() -> None:
    """Release Python and optional CUDA memory after spilling a clip to disk."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass
