"""Build per-gap transition specs for sequencing."""

from __future__ import annotations

CUT_XFADE_SECONDS = 0.04


def build_transitions(gap_count: int, kind: str, dissolve_duration: float) -> list[dict]:
    """Return one transition dict per gap between segments."""
    if gap_count < 1:
        return []

    if kind == "cut":
        return [{"type": "cut", "duration": CUT_XFADE_SECONDS} for _ in range(gap_count)]

    if kind == "dissolve":
        duration = max(0.1, float(dissolve_duration))
        return [{"type": "dissolve", "duration": duration} for _ in range(gap_count)]

    raise ValueError(f"Invalid transition {kind!r}. Use cut or dissolve.")


def uses_stream_copy(transitions: list[dict]) -> bool:
    """True when every gap is a hard cut (no dissolve)."""
    return all(item["type"] == "cut" for item in transitions)
