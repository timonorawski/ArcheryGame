"""
Browser-compatible models for WASM/pygbag environment.

These are dataclass-based replacements for the Pydantic models that don't
work in WASM (pydantic-core uses Rust which isn't WASM compatible).

The API is designed to be compatible with the original Pydantic models.
"""
from .primitives import (
    Point2D,
    Vector2D,
    Resolution,
    Color,
    Rectangle,
)

from .enums import (
    EventType,
    TargetState,
    GameState,
    EffectType,
)

# Export everything needed by games
__all__ = [
    # Primitives
    "Point2D",
    "Vector2D",
    "Resolution",
    "Color",
    "Rectangle",
    # Enums
    "EventType",
    "TargetState",
    "GameState",
    "EffectType",
]
