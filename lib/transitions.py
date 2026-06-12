"""Parse per-gap transition specs for fade-based sequencing."""

from __future__ import annotations

CUT_XFADE_SECONDS = 0.04


def parse_transitions(
    text: str,
    gap_count: int,
    *,
    default_dissolve_duration: float,
    default_gap: str = "dissolve",
) -> list[dict]:
    """Return transition dicts for each gap between segments (length == gap_count)."""
    if gap_count < 1:
        return []

    lines = [
        line.strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    transitions: list[dict] = []
    for index in range(gap_count):
        if index < len(lines):
            spec = lines[index]
        elif lines:
            spec = lines[-1]
        else:
            spec = default_gap

        transitions.append(_parse_transition_spec(spec, default_dissolve_duration))

    return transitions


def _parse_transition_spec(spec: str, default_dissolve_duration: float) -> dict:
    if spec == "cut":
        return {"type": "cut", "duration": CUT_XFADE_SECONDS}

    if spec.startswith("dissolve"):
        duration = default_dissolve_duration
        if ":" in spec:
            _, raw_duration = spec.split(":", 1)
            duration = max(0.1, float(raw_duration.strip()))
        return {"type": "dissolve", "duration": duration}

    raise ValueError(
        f"Invalid transition {spec!r}. Use cut, dissolve, or dissolve:seconds."
    )


def uses_stream_copy(transitions: list[dict]) -> bool:
    """True when every gap is a hard cut (no dissolve)."""
    return all(item["type"] == "cut" for item in transitions)
