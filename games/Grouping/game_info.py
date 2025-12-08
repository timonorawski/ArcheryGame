"""
Grouping - Game Info

Precision training game that measures shot grouping in real-time.
Required for auto-discovery by GameRegistry.
"""


def get_game_mode(**kwargs):
    """
    Factory function to create a GroupingMode instance.

    Args:
        **kwargs: Game configuration options

    Returns:
        GroupingMode instance
    """
    from games.Grouping.game_mode import GroupingMode
    return GroupingMode(**kwargs)
