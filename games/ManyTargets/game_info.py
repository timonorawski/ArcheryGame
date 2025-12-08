"""
ManyTargets - Game Info

Field clearance game - clear all targets while avoiding misses.
Required for auto-discovery by GameRegistry.
"""


def get_game_mode(**kwargs):
    """
    Factory function to create a ManyTargetsMode instance.

    Args:
        **kwargs: Game configuration options

    Returns:
        ManyTargetsMode instance
    """
    from games.ManyTargets.game_mode import ManyTargetsMode
    return ManyTargetsMode(**kwargs)
