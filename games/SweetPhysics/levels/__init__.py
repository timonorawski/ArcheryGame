"""Level system for Sweet Physics."""
from games.SweetPhysics.levels.loader import (
    SweetPhysicsLevelLoader,
    LevelData,
    ElementData,
    StarRequirements,
    create_default_level,
)

# Backwards compatibility
LevelLoader = SweetPhysicsLevelLoader

__all__ = [
    'SweetPhysicsLevelLoader',
    'LevelLoader',  # Backwards compatibility
    'LevelData',
    'ElementData',
    'StarRequirements',
    'create_default_level',
]
