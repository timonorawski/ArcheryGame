"""
Balloon Pop - Game Info

This file defines the game's metadata and provides the factory function
for creating game instances. Required for auto-discovery by GameRegistry.
"""


def get_game_mode(**kwargs):
    """
    Factory function to create a BalloonPopMode instance.

    Args:
        **kwargs: Game configuration options (from CLI or AMS)

    Returns:
        BalloonPopMode instance
    """
    from games.BalloonPop.game_mode import BalloonPopMode
    return BalloonPopMode(**kwargs)
