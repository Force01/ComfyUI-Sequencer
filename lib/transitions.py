"""Editor-style transition palette mapped onto FFmpeg xfade."""

from __future__ import annotations

CUT_XFADE_SECONDS = 0.04

# UI name -> FFmpeg xfade transition. "cut" is special-cased (stream copy,
# no re-encode). xfade's own "dissolve" is a noisy pixel dissolve; the
# classic editor dissolve is xfade "fade".
XFADE_NAMES = {
    "dissolve": "fade",
    "fade to black": "fadeblack",
    "fade to white": "fadewhite",
    "wipe left": "wipeleft",
    "wipe right": "wiperight",
    "wipe up": "wipeup",
    "wipe down": "wipedown",
    "slide left": "slideleft",
    "slide right": "slideright",
    "slide up": "slideup",
    "slide down": "slidedown",
    "circle open": "circleopen",
    "circle close": "circleclose",
    "pixelate": "pixelize",
    "zoom in": "zoomin",
    "blur": "hblur",
}

TRANSITION_NAMES = ["cut", *XFADE_NAMES]


def build_transitions(gap_count: int, kind: str, duration: float) -> list[dict]:
    """Return one transition dict per gap between segments."""
    if gap_count < 1:
        return []

    if kind == "cut":
        spec = {"type": "cut", "xfade": "fade", "duration": CUT_XFADE_SECONDS}
    elif kind in XFADE_NAMES:
        spec = {"type": kind, "xfade": XFADE_NAMES[kind], "duration": max(0.1, float(duration))}
    else:
        raise ValueError(
            f"Invalid transition {kind!r}. Use one of: {', '.join(TRANSITION_NAMES)}."
        )

    return [dict(spec) for _ in range(gap_count)]


def uses_stream_copy(transitions: list[dict]) -> bool:
    """True when every gap is a hard cut (no re-encode needed)."""
    return all(item["type"] == "cut" for item in transitions)
