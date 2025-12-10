"""BrickBreaker NextGen - Lua behavior-driven brick breaker."""

# Note: Don't import game_mode here to avoid circular imports during discovery.
# The registry imports game_mode.py directly.

__all__ = ['BrickBreakerNGMode']


def get_game_mode():
    """Lazy import to avoid circular dependency."""
    from .game_mode import BrickBreakerNGMode
    return BrickBreakerNGMode
