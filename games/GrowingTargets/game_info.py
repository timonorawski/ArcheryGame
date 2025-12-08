"""GrowingTargets - Game Info

Speed/accuracy tradeoff game where targets grow over time.
Hit them small for maximum points, or wait for an easier shot.
"""


def get_game_mode(**kwargs):
    """Factory function to create game instance."""
    from games.GrowingTargets.game_mode import GrowingTargetsMode
    return GrowingTargetsMode(**kwargs)
