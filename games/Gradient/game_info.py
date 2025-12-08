"""Game info factory for Gradient Test."""


def get_game_mode(**kwargs):
    """Factory function to create game mode instance."""
    from games.Gradient.game_mode import GradientMode
    return GradientMode(**kwargs)
