"""Shared mocks and package bootstrap for ComfyUI-only dependencies."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
PKG_NAME = "comfyui_sequencer"


def _install_comfy_mocks() -> None:
    if "folder_paths" in sys.modules:
        return

    folder_paths = ModuleType("folder_paths")
    folder_paths.folder_names_and_paths = {
        "text_encoders": ([], set()),
    }
    folder_paths.filename_list_cache = {}
    folder_paths.cache_helper = MagicMock()

    folder_paths.get_temp_directory = lambda: "/tmp/comfyui"
    folder_paths.get_output_directory = lambda: "/tmp/comfyui/output"
    folder_paths.get_input_directory = lambda: "/tmp/comfyui/input"
    folder_paths.exists_annotated_filepath = lambda _path: False
    folder_paths.get_annotated_filepath = lambda path: path
    folder_paths.get_save_image_path = lambda *_args, **_kwargs: (
        "/tmp/comfyui/output",
        "sequence",
        1,
        "",
        "sequence",
    )
    sys.modules["folder_paths"] = folder_paths

    comfy_api = ModuleType("comfy_api")
    latest = ModuleType("comfy_api.latest")

    class _VideoCodec:
        H264 = "h264"

    class _VideoContainer:
        MP4 = "mp4"

    class _InputImpl:
        class VideoFromFile:
            def __init__(self, path: str) -> None:
                self.path = path

    class _ComfyExtension:
        pass

    class _ComfyNode:
        pass

    class _Schema:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _NodeOutput:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

    class _IO:
        Schema = _Schema
        NodeOutput = _NodeOutput
        ComfyNode = _ComfyNode
        ComfyExtension = _ComfyExtension

        class Hidden:
            prompt = "prompt"
            extra_pnginfo = "extra_pnginfo"

        class Video:
            @staticmethod
            def Input(*_args, **_kwargs):
                return MagicMock()

            @staticmethod
            def Output(*_args, **_kwargs):
                return MagicMock()

        class Combo:
            @staticmethod
            def Input(*_args, **_kwargs):
                return MagicMock()

        class Float:
            @staticmethod
            def Input(*_args, **_kwargs):
                return MagicMock()

        class String:
            @staticmethod
            def Input(*_args, **_kwargs):
                return MagicMock()

        class Autogrow:
            class TemplateNames:
                def __init__(self, *_args, **kwargs) -> None:
                    self.kwargs = kwargs

            class Type:
                pass

            @staticmethod
            def Input(*_args, **_kwargs):
                return MagicMock()

    class _UI:
        class PreviewVideo:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

        class SavedResult:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

        class FolderType:
            output = "output"

    latest.InputImpl = _InputImpl
    latest.ComfyExtension = _ComfyExtension
    latest.io = _IO
    latest.ui = _UI
    latest.VideoCodec = _VideoCodec
    latest.VideoContainer = _VideoContainer

    comfy_api.latest = latest
    sys.modules["comfy_api"] = comfy_api
    sys.modules["comfy_api.latest"] = latest


def _load_module(module_name: str, file_path: Path) -> ModuleType:
    existing = sys.modules.get(module_name)
    if existing is not None and getattr(existing, "__file__", None) == str(file_path):
        return existing

    parent_name = module_name.rpartition(".")[0]
    if parent_name and parent_name not in sys.modules:
        parent_path = file_path.parent
        if parent_path.name in ("lib", "nodes"):
            parent_pkg = types.ModuleType(parent_name)
            parent_pkg.__path__ = [str(parent_path)]
            parent_pkg.__package__ = parent_name
            sys.modules[parent_name] = parent_pkg

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = parent_name or PKG_NAME
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_package() -> ModuleType:
    """Load the repo as a synthetic package (directory name contains a hyphen)."""
    if PKG_NAME in sys.modules and hasattr(sys.modules[PKG_NAME], "comfy_entrypoint"):
        return sys.modules[PKG_NAME]

    for sub in ("lib", "nodes"):
        sub_name = f"{PKG_NAME}.{sub}"
        if sub_name not in sys.modules:
            sub_pkg = types.ModuleType(sub_name)
            sub_pkg.__path__ = [str(ROOT / sub)]
            sub_pkg.__package__ = sub_name
            sys.modules[sub_name] = sub_pkg

    _load_module(f"{PKG_NAME}.lib.transitions", ROOT / "lib" / "transitions.py")
    _load_module(f"{PKG_NAME}.lib.sequence", ROOT / "lib" / "sequence.py")
    _load_module(f"{PKG_NAME}.lib.paths", ROOT / "lib" / "paths.py")
    _load_module(f"{PKG_NAME}.nodes.spill", ROOT / "nodes" / "spill.py")
    _load_module(f"{PKG_NAME}.nodes.sequencer", ROOT / "nodes" / "sequencer.py")
    return _load_module(PKG_NAME, ROOT / "__init__.py")


def pytest_configure(config):
    _install_comfy_mocks()
    pkg = load_package()
    # Pytest may import the repo-root __init__.py as a top-level module during
    # collection; alias it to the synthetic package so relative imports work.
    sys.modules.setdefault("__init__", pkg)


def pytest_ignore_collect(collection_path, config):
    if collection_path.name == "__init__.py" and collection_path.parent.resolve() == ROOT.resolve():
        return True
    return False
