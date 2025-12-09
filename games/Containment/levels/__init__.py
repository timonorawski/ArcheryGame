"""Containment game levels module.

Provides level loading and management for the Containment game.
"""
from .level_loader import (
    # Level loader class (for BaseGame integration)
    ContainmentLevelLoader,

    # Data classes
    LevelConfig,
    Objectives,
    BallConfig,
    Environment,
    EdgeConfig,
    GapConfig,
    SpinnerConfig,
    HitModes,
    HitModeConfig,
    CaptureZone,

    # Loading functions (legacy, for backwards compatibility)
    load_level,
    apply_pacing_overrides,
    list_levels,
    get_level_info,
    get_levels_dir,

    # Hit mode resolution
    resolve_hit_mode_angle,
    resolve_random_value,
    shape_name_to_sides,
)

__all__ = [
    # Level loader class
    "ContainmentLevelLoader",

    # Data classes
    "LevelConfig",
    "Objectives",
    "BallConfig",
    "Environment",
    "EdgeConfig",
    "GapConfig",
    "SpinnerConfig",
    "HitModes",
    "HitModeConfig",
    "CaptureZone",

    # Loading functions (legacy)
    "load_level",
    "apply_pacing_overrides",
    "list_levels",
    "get_level_info",
    "get_levels_dir",

    # Hit mode resolution
    "resolve_hit_mode_angle",
    "resolve_random_value",
    "shape_name_to_sides",
]
