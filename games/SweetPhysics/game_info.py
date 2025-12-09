"""Game info factory for Sweet Physics."""
import sys


def get_game_mode(**kwargs):
    """Factory function to create game mode instance."""
    try:
        from games.SweetPhysics.game_mode import SweetPhysicsMode
        return SweetPhysicsMode(**kwargs)
    except Exception as e:
        import traceback
        error_msg = f"Failed to import SweetPhysicsMode: {e}\n{traceback.format_exc()}"
        print(error_msg)
        if sys.platform == "emscripten":
            try:
                import platform
                platform.window.console.error(error_msg)
            except:
                pass
        raise
