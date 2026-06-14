from .nodes.sequencer import comfy_entrypoint

# Allow GGUF files to appear in the text_encoders file picker so that nodes
# like LTXAVTextEncoderLoader can select a quantized Gemma GGUF directly.
try:
    import folder_paths as _fp
    _paths, _exts = _fp.folder_names_and_paths.get("text_encoders", ([], set()))
    _exts.add(".gguf")
    # Invalidate both caches so the new extension takes effect immediately
    _fp.filename_list_cache.pop("text_encoders", None)
    _fp.cache_helper.clear()
except Exception:
    pass

__all__ = ["comfy_entrypoint"]
