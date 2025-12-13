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
    # IDE mode: ?mode=ide skips auto-loading game and waits for IDE to send files

    # Debug: log the raw URL
    if sys.platform == "emscripten":
        try:
            import platform as browser_platform
            raw_href = browser_platform.window.location.href
            raw_search = browser_platform.window.location.search
            js_log(f"[main.py] URL DEBUG: href={raw_href}")
            js_log(f"[main.py] URL DEBUG: search={raw_search}")
        except Exception as e:
            js_log(f"[main.py] URL DEBUG error: {e}")

    ide_mode = get_url_param('mode', None) == 'ide'
    js_log(f"[main.py] ide_mode={ide_mode}")
    game_slug = get_url_param('game', None if ide_mode else 'containment')
    level_slug = get_url_param('level', None)
    level_group = get_url_param('level_group', None)

    # IDE mode: wait for files before loading game
    if ide_mode and sys.platform == "emscripten":
        import platform as browser_platform
        import json
        js_log("[main.py] IDE mode - waiting for project files...")

        # Initialize IDE bridge and ContentFS
        from ams.content_fs_browser import get_content_fs
        from ide_bridge import init_bridge

        content_fs = get_content_fs()

        # Wait for IDE bridge JS to be ready
        for _ in range(50):  # Max 5 seconds
            if hasattr(browser_platform.window, 'ideBridge'):
                break
            await asyncio.sleep(0.1)

        if not hasattr(browser_platform.window, 'ideBridge'):
            js_log("[main.py] ERROR: IDE bridge not available")
            return

        # Signal ready to IDE
        browser_platform.window.ideBridge.sendToIDEFromPython('ready', json.dumps({'waitingForFiles': True}))
        js_log("[main.py] Signaled ready, waiting for files...")

        # Wait for files message
        ide_bridge = None
        project_path = None
        for _ in range(600):  # Max 60 seconds
            if hasattr(browser_platform.window, 'ideMessages'):
                messages = browser_platform.window.ideMessages
                while messages.length > 0:
                    js_msg = messages.shift()
                    if js_msg is not None:
                        msg_json = browser_platform.window.JSON.stringify(js_msg)
                        msg = json.loads(msg_json)
                        js_log(f"[main.py] IDE message: {msg.get('type')}")

                        if msg.get('type') == 'files':
                            # Initialize bridge if needed
                            if ide_bridge is None:
                                ide_bridge = init_bridge(content_fs, None)
                                project_path = ide_bridge.get_project_path()
                                js_log(f"[main.py] IDE bridge initialized, project: {project_path}")

                            # Write files
                            files = msg.get('files', {})
                            result = ide_bridge.receive_files(json.dumps(files))
                            js_log(f"[main.py] Files written: {result}")

                        elif msg.get('type') == 'reload' and project_path:
                            # Files received, now load the game
                            js_log("[main.py] Reload requested, loading game...")
                            break
                else:
                    # No break, continue waiting
                    await asyncio.sleep(0.1)
                    continue
                # Break from outer loop if inner loop broke
                break
            await asyncio.sleep(0.1)

        if not project_path:
            js_log("[main.py] ERROR: No files received from IDE")
            return

        # Load game from IDE project
        js_log("[main.py] Creating runtime and loading IDE project...")
        runtime = BrowserGameRuntime(screen)

        # Add project as game layer and load
        from pathlib import Path

        try:
            from ams.games.game_engine import GameEngine
            js_log("[main.py] GameEngine imported successfully")
        except Exception as e:
            js_log(f"[main.py] ERROR importing GameEngine: {e}")
            import traceback
            traceback.print_exc()
            browser_platform.window.ideBridge.notifyError(f"Import error: {e}", None, None)
            return

        content_fs.add_game_layer(project_path)
        game_json_path = Path(project_path) / "game.json"

        if game_json_path.exists():
            try:
                game_class = GameEngine.from_yaml(game_json_path)
                runtime.game = game_class(
                    content_fs=content_fs,
                    width=runtime.width,
                    height=runtime.height
                )
                runtime.game_slug = 'ide_project'
                runtime._ide_mode = True
                js_log(f"[main.py] IDE game loaded: {runtime.game.NAME}")

                # Notify IDE
                browser_platform.window.ideBridge.notifyReloaded()
            except Exception as e:
                js_log(f"[main.py] ERROR loading game: {e}")
                import traceback
                traceback.print_exc()
                browser_platform.window.ideBridge.notifyError(str(e), None, None)
        else:
            js_log(f"[main.py] ERROR: No game.json at {game_json_path}")
            return

    else:
        # Normal mode: create runtime and load game
        js_log("[main.py] Creating BrowserGameRuntime...")
        runtime = BrowserGameRuntime(screen)

        if game_slug:
            js_log(f"[main.py] Loading game: {game_slug}")
            await runtime.load_game(game_slug, level=level_slug, level_group=level_group)
            js_log("[main.py] Game loaded, starting run loop...")

    await runtime.run()

    pygame.quit()


# Pygbag requires asyncio.run(main()) at module level
asyncio.run(main())
