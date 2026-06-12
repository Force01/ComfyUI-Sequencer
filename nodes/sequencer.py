"""Video Sequencer node — join MP4 clips end-to-end with FFmpeg."""

from __future__ import annotations

import os

from typing_extensions import override

import folder_paths
from comfy_api.latest import ComfyExtension, InputImpl, io, ui

from ..lib.paths import ordered_segment_paths
from ..lib.sequence import require_ffmpeg, sequence_videos
from ..lib.transitions import TRANSITION_NAMES, build_transitions

_MAX_SEGMENTS = 20


class VideoSequencer(io.ComfyNode):
    """Join multiple MP4 video clips end-to-end into a single MP4."""

    @classmethod
    def define_schema(cls) -> io.Schema:
        # Autogrow: segment0/segment1/... slots that grow as clips are connected.
        segments_template = io.Autogrow.TemplatePrefix(
            io.Video.Input(
                "segment",
                tooltip=(
                    "Clip in playback order. Connect any VIDEO output — "
                    "Load Video or a clip generated earlier in the workflow."
                ),
            ),
            prefix="segment",
            min=2,
            max=_MAX_SEGMENTS,
        )
        return io.Schema(
            node_id="VideoSequencer",
            display_name="Video Sequencer",
            category="video/edit",
            description=(
                "Join video clips end-to-end into one continuous video, in slot "
                "order. Accepts any VIDEO output — loaded files or clips "
                "generated earlier in the workflow. A new segment slot appears "
                "whenever you connect a clip (up to 20). Pick a transition for "
                "the junctions: 'cut' joins instantly with no re-encode; "
                "dissolves, fades, wipes, and slides re-encode."
            ),
            search_aliases=[
                "sequence",
                "concat",
                "stitch",
                "join",
                "merge clips",
                "dissolve",
                "fade",
                "xfade",
                "video segments",
                "split renders",
                "stream copy",
            ],
            inputs=[
                io.Autogrow.Input(
                    "segments",
                    template=segments_template,
                    tooltip=(
                        "Clips to stitch, played in slot order (segment0 first). "
                        "A new empty slot appears whenever you connect a clip."
                    ),
                ),
                io.Combo.Input(
                    "join_mode",
                    display_name="transition",
                    options=TRANSITION_NAMES,
                    default="cut",
                    tooltip=(
                        "Transition used at every junction between clips. "
                        "cut: hard cuts, instant and lossless (no re-encode). "
                        "All others re-encode to H.264. For different "
                        "transitions at different junctions, chain Video "
                        "Sequencer nodes."
                    ),
                ),
                io.Float.Input(
                    "dissolve_duration",
                    default=0.5,
                    min=0.1,
                    max=10.0,
                    step=0.05,
                    display_name="transition seconds",
                    tooltip="How long each transition lasts, in seconds (ignored for cut).",
                ),
                io.String.Input(
                    "filename_prefix",
                    default="sequence",
                    tooltip="Output filename prefix under ComfyUI output/.",
                ),
            ],
            outputs=[
                io.Video.Output(display_name="video"),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def execute(
        cls,
        segments: io.Autogrow.Type,
        join_mode: str,
        dissolve_duration: float,
        filename_prefix: str,
    ) -> io.NodeOutput:
        require_ffmpeg()
        resolved = ordered_segment_paths(segments)
        transition_specs = build_transitions(
            max(0, len(resolved) - 1),
            join_mode,
            dissolve_duration,
        )
        join_mode = "stream_copy" if join_mode == "cut" else "fade"

        full_output_folder, filename, counter, subfolder, _prefix = folder_paths.get_save_image_path(
            filename_prefix,
            folder_paths.get_output_directory(),
            512,
            512,
        )
        out_name = f"{filename}_{counter:05}_.mp4"
        out_path = os.path.join(full_output_folder, out_name)

        stitched = sequence_videos(
            resolved,
            out_path,
            join_mode=join_mode,
            transitions=transition_specs,
        )
        video = InputImpl.VideoFromFile(stitched)

        return io.NodeOutput(
            video,
            ui=ui.PreviewVideo([ui.SavedResult(out_name, subfolder, io.FolderType.output)]),
        )


class SequencerExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [VideoSequencer]


async def comfy_entrypoint() -> SequencerExtension:
    return SequencerExtension()
