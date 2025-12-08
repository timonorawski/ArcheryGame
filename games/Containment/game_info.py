"""Containment - Game Info

Adversarial geometry-building game where you place deflectors to contain
a ball trying to escape through gaps.
"""


def get_game_mode(**kwargs):
    """Factory function to create game instance."""
    from games.Containment.game_mode import ContainmentMode
    return ContainmentMode(**kwargs)
