"""Containment - Game Info

Adversarial geometry-building game where you place deflectors to contain
a ball trying to escape through gaps.
"""
import sys


def get_game_mode(**kwargs):
    """Factory function to create game instance."""
    try:
        from games.Containment.game_mode import ContainmentMode
        return ContainmentMode(**kwargs)
    except Exception as e:
        import traceback
        error_msg = f"Failed to import ContainmentMode: {e}\n{traceback.format_exc()}"
        print(error_msg)
        # Also log to JS console if in browser
        if sys.platform == "emscripten":
            try:
                import platform
                platform.window.console.error(error_msg)
            except:
                pass
        raise
