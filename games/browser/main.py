"""
AMS Games Browser Entry Point

This is the main entry point for running AMS games in the browser via pygbag.
Pygbag compiles this to WebAssembly, allowing pygame games to run in browsers.

Usage (development):
    python -m pygbag games/browser/main.py

Usage (build):
    python -m pygbag --build games/browser/main.py
"""
# pygbag: requirements
# (no additional requirements - games using native libs like pymunk are excluded)

import asyncio
import sys

# Pygame must be imported before other game modules
import pygame

# Add project root to path for imports
if sys.platform != "emscripten":
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def js_log(msg):
    """Log to browser console in addition to Python stdout."""
    print(msg)
    if sys.platform == "emscripten":
        try:
            import platform
            platform.window.console.log(msg)
        except:
            pass


async def main():
    """Main async entry point for browser games."""
    js_log("[main.py] Starting AMS Games...")

    pygame.init()
    pygame.display.set_caption("AMS Games")

    # Default resolution - will be responsive in browser
    screen = pygame.display.set_mode((1280, 720))

    js_log("[main.py] Pygame initialized, screen created")

    # Import runtime after pygame init
    try:
        from game_runtime import BrowserGameRuntime, inject_fengari_scripts
        from platform_compat import get_url_param
        js_log("[main.py] Runtime modules imported")

        # Inject Fengari scripts for YAML game Lua support
        inject_fengari_scripts()
        js_log("[main.py] Fengari injection initiated")

        # Wait for Fengari bridge to be ready before loading game
        if sys.platform == "emscripten":
            import platform as browser_platform
            js_log("[main.py] Waiting for Fengari bridge...")
            for _ in range(100):  # Max 10 seconds
                # Check for fengariBridgeReady (also sets wasmoonBridgeReady for compat)
                if getattr(browser_platform.window, 'fengariBridgeReady', False):
                    js_log("[main.py] Fengari bridge ready!")
                    break
                await asyncio.sleep(0.1)
            else:
                js_log("[main.py] WARNING: Fengari bridge not ready after 10s")
    except Exception as e:
        js_log(f"[main.py] ERROR importing runtime: {e}")
        import traceback
        traceback.print_exc()
        # Keep running with error display
        clock = pygame.time.Clock()
        font = pygame.font.Font(None, 32)
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
            screen.fill((40, 0, 0))
            text = font.render(f"Import Error: {e}", True, (255, 100, 100))
            screen.blit(text, (50, 50))
            pygame.display.flip()
            await asyncio.sleep(0)
            clock.tick(30)

    # Get game selection from URL params or default
    game_slug = get_url_param('game', 'containment')
    level_slug = get_url_param('level', None)
    level_group = get_url_param('level_group', None)

    js_log(f"[main.py] Loading game: {game_slug}")

    # Create and run the game runtime
    js_log("[main.py] Creating BrowserGameRuntime...")
    runtime = BrowserGameRuntime(screen)
    js_log("[main.py] BrowserGameRuntime created, calling load_game...")
    await runtime.load_game(game_slug, level=level_slug, level_group=level_group)
    js_log("[main.py] load_game complete, starting run loop...")

    # Signal to IDE that engine is ready (game loaded, about to start loop)
    if sys.platform == "emscripten":
        try:
            import platform as browser_platform
            # Wait briefly for IDE bridge to load (injected in inject_fengari_scripts)
            for _ in range(20):  # Max 2 seconds
                if hasattr(browser_platform.window, 'ideBridge'):
                    break
                await asyncio.sleep(0.1)

            if hasattr(browser_platform.window, 'ideBridge'):
                browser_platform.window.ideBridge.sendToIDE('ready', {
                    'game': game_slug,
                    'engineReady': True
                })
                js_log("[main.py] Sent engine ready signal to IDE")
            else:
                js_log("[main.py] IDE bridge not available (standalone mode)")
        except Exception as e:
            js_log(f"[main.py] Could not send ready signal: {e}")

    await runtime.run()

    pygame.quit()


# Pygbag requires asyncio.run(main()) at module level
asyncio.run(main())
