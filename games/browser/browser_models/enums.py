"""
Browser-compatible enums for WASM environment.
"""
from enum import Enum


class EventType(str, Enum):
    """Type of input event."""
    HIT = "hit"
    MISS = "miss"


class TargetState(str, Enum):
    """State of a game target."""
    ACTIVE = "active"
    HIT = "hit"
    ESCAPED = "escaped"
    EXPIRED = "expired"


class GameState(str, Enum):
    """Overall game state."""
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    LEVEL_COMPLETE = "level_complete"


class EffectType(str, Enum):
    """Type of visual effect."""
    HIT = "hit"
    MISS = "miss"
    SCORE = "score"
    COMBO = "combo"
