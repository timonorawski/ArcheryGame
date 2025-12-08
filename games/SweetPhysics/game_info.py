"""Game info factory for Sweet Physics."""


def get_game_mode(**kwargs):
    """Factory function to create game mode instance."""
    from games.SweetPhysics.game_mode import SweetPhysicsMode
    return SweetPhysicsMode(**kwargs)
