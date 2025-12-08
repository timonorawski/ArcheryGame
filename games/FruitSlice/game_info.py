"""FruitSlice - Game Info

Fruit Ninja-style game with arcing targets and combo system.
Supports multiple pacing presets for different input devices.
"""


def get_game_mode(**kwargs):
    """Factory function to create game instance."""
    from games.FruitSlice.game_mode import FruitSliceMode

    # Handle mode shortcuts
    mode = kwargs.get('mode', 'classic')
    if mode == 'zen':
        kwargs['no_bombs'] = True

    return FruitSliceMode(**kwargs)
