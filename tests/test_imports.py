"""Package import and ComfyUI registration smoke tests."""

from __future__ import annotations

import asyncio
import sys

import folder_paths

from conftest import PKG_NAME, load_package


def test_package_exports_comfy_entrypoint():
    pkg = load_package()
    assert hasattr(pkg, "comfy_entrypoint")
    assert pkg.__all__ == ["comfy_entrypoint"]


def test_import_does_not_patch_text_encoder_gguf():
    _, exts = folder_paths.folder_names_and_paths["text_encoders"]
    assert ".gguf" not in exts


def test_sequencer_node_mapping_loads():
    from comfyui_sequencer.lib.transitions import TRANSITION_NAMES
    from comfyui_sequencer.nodes.sequencer import VideoSequencer, comfy_entrypoint

    schema = VideoSequencer.define_schema()
    assert schema.kwargs["node_id"] == "Sequencer_VideoSequencer"
    assert schema.kwargs["category"] == "video/edit"
    assert "cut" in TRANSITION_NAMES

    extension = asyncio.run(comfy_entrypoint())
    nodes = asyncio.run(extension.get_node_list())
    node_ids = {node.define_schema().kwargs["node_id"] for node in nodes}
    assert node_ids == {"Sequencer_VideoSequencer", "Sequencer_SpillClipToDisk"}


def test_reimport_is_idempotent():
    pkg1 = load_package()
    pkg2 = load_package()
    assert pkg1 is pkg2
    _, exts = folder_paths.folder_names_and_paths["text_encoders"]
    assert ".gguf" not in exts


def test_spill_cleanup_cpu_only(monkeypatch):
    from unittest.mock import MagicMock

    import torch

    from comfyui_sequencer.nodes.spill import _release_clip_memory

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    empty_cache = MagicMock()
    ipc_collect = MagicMock()
    monkeypatch.setattr(torch.cuda, "empty_cache", empty_cache)
    monkeypatch.setattr(torch.cuda, "ipc_collect", ipc_collect)
    _release_clip_memory()
    empty_cache.assert_not_called()
    ipc_collect.assert_not_called()
