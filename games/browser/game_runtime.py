"""
Browser Game Runtime

Async game loop wrapper for running AMS games in the browser.
Handles the main loop, input processing, and JS bridge communication.
"""
import asyncio
import json
import sys
import time
from typing import Optional

import pygame

# Conditional imports for browser environment
if sys.platform == "emscripten":
    import platform as browser_platform


def js_log(msg):
    """Log to browser console."""
    print(msg)
    if sys.platform == "emscripten":
        try:
            browser_platform.window.console.log(msg)
        except:
            pass


class BrowserGameRuntime:
    """
    Manages the game lifecycle in the browser.

    Responsibilities:
    - Async game loop with browser yield
    - Game instantiation via registry
    - Input event processing
    - JS bridge communication (postMessage)
    - State broadcasting to parent frame
    """

    def __init__(self, screen: pygame.Surface):
        """
        Initialize the browser runtime.

        Args:
            screen: Pygame display surface
        """
        # Log build ID for cache verification
        try:
            build_id = open("build_id.txt").read().strip()
            js_log(f"[BrowserGameRuntime] BUILD ID: {build_id}")
        except:
            js_log("[BrowserGameRuntime] BUILD ID: unknown")

        js_log("[BrowserGameRuntime] __init__ starting...")
        self.screen = screen
        self.width = screen.get_width()
        self.height = screen.get_height()
        self.running = True
        self.game = None
        self.game_slug = None
        js_log(f"[BrowserGameRuntime] screen size: {self.width}x{self.height}")

        # Import here to avoid circular imports
        js_log("[BrowserGameRuntime] Importing BrowserInputAdapter...")
        from input_adapter import BrowserInputAdapter
        js_log("[BrowserGameRuntime] Creating BrowserInputAdapter...")
        self.input_adapter = BrowserInputAdapter(self.width, self.height)
        js_log("[BrowserGameRuntime] BrowserInputAdapter created")

        # State tracking for efficient updates
        self._last_state_broadcast = 0
        self._state_broadcast_interval = 0.1  # 10Hz state updates to JS
        self._load_error: Optional[str] = None  # Track loading errors for display

        # IDE bridge for Monaco editor integration
        self._ide_bridge = None
        self._ide_mode = False

        # Signal ready to JS
        js_log("[BrowserGameRuntime] Sending ready signal...")
        self._send_ready_signal()

        # Initialize IDE bridge for Monaco editor integration
        js_log("[BrowserGameRuntime] Initializing IDE bridge...")
        self._init_ide_bridge()

        js_log("[BrowserGameRuntime] __init__ complete")

    def _send_ready_signal(self):
        """Signal to JavaScript that the runtime is ready."""
        self._send_to_js('ready', {
            'width': self.width,
            'height': self.height,
        })

    async def load_game(
        self,
        game_slug: str,
        level: Optional[str] = None,
        level_group: Optional[str] = None,
    ):
        """
        Load a game by slug.

        Args:
            game_slug: Game identifier (e.g., 'containment', 'sweetphysics')
            level: Optional level slug to load
            level_group: Optional level group to play through
        """
        # Import registry (deferred to avoid import issues during pygbag bundling)
        js_log(f"[BrowserGameRuntime] Loading game: {game_slug}")
        try:
            import os
            from ams.content_fs_browser import get_content_fs
            from games.registry import GameRegistry
            content_fs = get_content_fs()
            js_log(f"[BrowserGameRuntime] ContentFS created: {content_fs.describe_layers()}")

            # Debug: enumerate filesystem
            js_log(f"[FS DEBUG] core_dir: {content_fs.core_dir}")
            js_log(f"[FS DEBUG] cwd: {os.getcwd()}")
            for root_item in ['/', '/data', '/data/data', '/data/data/web', '/data/data/web/assets']:
                if os.path.exists(root_item):
                    try:
                        contents = os.listdir(root_item)[:15]
                        js_log(f"[FS DEBUG] {root_item}/: {contents}")
                    except Exception as e:
                        js_log(f"[FS DEBUG] {root_item}/ error: {e}")

            games_dir = content_fs.core_dir / 'games'
            js_log(f"[FS DEBUG] games_dir: {games_dir}, exists: {games_dir.exists()}")
            if games_dir.exists():
                for item in games_dir.iterdir():
                    if item.is_dir():
                        try:
                            contents = [f.name for f in list(item.iterdir())[:10]]
                            js_log(f"[FS DEBUG]   {item.name}/: {contents}")

                            # Test specific file existence for YAML games
                            if item.name in ['BrickBreakerNG', 'LoveOMeterNG']:
                                json_path = item / 'game.json'
                                json_path_str = str(json_path)
                                js_log(f"[FS DEBUG]   -> json_path: {json_path_str}")
                                js_log(f"[FS DEBUG]   -> Path.exists(): {json_path.exists()}")
                                js_log(f"[FS DEBUG]   -> os.path.exists(): {os.path.exists(json_path_str)}")
                                js_log(f"[FS DEBUG]   -> os.path.isfile(): {os.path.isfile(json_path_str)}")
                        except Exception as e:
                            js_log(f"[FS DEBUG]   {item.name}/ error: {e}")

            # Test: Try to register YAML game directly to see error
            yaml_game_dir = games_dir / 'BrickBreakerNG'
            json_path = yaml_game_dir / 'game.json'
            js_log(f"[FS DEBUG] Trying to load GameEngine from {json_path}")
            try:
                from ams.games.game_engine import GameEngine
                js_log(f"[FS DEBUG] GameEngine imported")
                game_class = GameEngine.from_yaml(json_path)
                js_log(f"[FS DEBUG] GameEngine.from_yaml succeeded: {game_class}")
            except Exception as e:
                import traceback
                js_log(f"[FS DEBUG] GameEngine.from_yaml FAILED: {e}")
                js_log(f"[FS DEBUG] Traceback: {traceback.format_exc()}")

            registry = GameRegistry(content_fs)
            js_log(f"[BrowserGameRuntime] Registry loaded, available games: {list(registry._games.keys())}")
        except ImportError as e:
            self._load_error = f'Failed to load game registry: {e}'
            js_log(f"[BrowserGameRuntime] ERROR: {self._load_error}")
            self._send_to_js('error', {'message': self._load_error})
            return

        try:
            js_log(f"[BrowserGameRuntime] Creating game instance...")
            self.game = registry.create_game(
                game_slug,
                self.width,
                self.height,
                level=level,
                level_group=level_group,
            )
            self.game_slug = game_slug
            js_log(f"[BrowserGameRuntime] Game '{game_slug}' loaded successfully")
            self._send_to_js('game_loaded', {
                'game': game_slug,
                'name': self.game.NAME,
                'level': level,
                'level_group': level_group,
            })
        except Exception as e:
            import traceback
            self._load_error = f'Failed to load game: {e}'
            js_log(f"[BrowserGameRuntime] ERROR: {self._load_error}")
            traceback.print_exc()
            self._send_to_js('error', {'message': self._load_error})

    async def run(self):
        """
        Main async game loop.

        CRITICAL: Must await asyncio.sleep(0) each frame to yield to browser.
        """
        js_log(f"[BrowserGameRuntime] Starting game loop, game={self.game}, error={self._load_error}")
        clock = pygame.time.Clock()
        frame_count = 0

        while self.running:
            frame_count += 1
            if frame_count == 1:
                js_log(f"[BrowserGameRuntime] First frame, game is {'loaded' if self.game else 'None'}")
            dt = clock.tick(60) / 1000.0  # Delta time in seconds

            # Process pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    continue

                # Debug: log mouse events
                if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION):
                    if frame_count % 60 == 0 or event.type == pygame.MOUSEBUTTONDOWN:
                        js_log(f"[Runtime] pygame event: type={event.type} pos={getattr(event, 'pos', 'N/A')}")

                # Let input adapter handle the event
                self.input_adapter.handle_pygame_event(event)

                # Let game handle raw pygame events if it needs to
                if self.game and hasattr(self.game, 'handle_pygame_event'):
                    self.game.handle_pygame_event(event)

            # Process messages from JavaScript
            await self._process_js_messages()

            # Process IDE messages (Monaco editor integration)
            await self._process_ide_messages()

            # Run game loop if we have a game
            if self.game:
                # Get input events and pass to game
                input_events = self.input_adapter.get_events()
                self.game.handle_input(input_events)

                # Update game state
                self.game.update(dt)

                # Render game
                self.game.render(self.screen)

                # Broadcast state to JS periodically
                now = time.monotonic()
                if now - self._last_state_broadcast >= self._state_broadcast_interval:
                    self._broadcast_game_state()
                    self._last_state_broadcast = now
            else:
                # No game loaded - show loading screen
                self._render_loading_screen()

            # Update display
            pygame.display.flip()

            # CRITICAL: Yield to browser event loop
            await asyncio.sleep(0)

    async def _process_js_messages(self):
        """Process pending messages from JavaScript."""
        if sys.platform != "emscripten":
            return

        # Check for messages in the global message queue
        try:
            if hasattr(browser_platform.window, 'gameMessages'):
                messages = browser_platform.window.gameMessages
                while len(messages) > 0:
                    msg_str = messages.pop(0)
                    try:
                        msg = json.loads(msg_str)
                        await self._handle_js_message(msg)
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

        # Process WASMOON Lua results
        self._process_lua_results()

    async def _handle_js_message(self, msg: dict):
        """
        Handle a message from JavaScript.

        Supported message types:
        - load_game: Load a different game
        - load_level: Load level from YAML string (authoring mode)
        - action: Execute game action (retry, next, etc.)
        - pause: Pause the game
        - resume: Resume the game
        """
        msg_type = msg.get('type', '')

        if msg_type == 'load_game':
            game_slug = msg.get('game')
            level = msg.get('level')
            level_group = msg.get('level_group')
            if game_slug:
                await self.load_game(game_slug, level=level, level_group=level_group)

        elif msg_type == 'load_level':
            yaml_content = msg.get('yaml', '')
            self._apply_level_yaml(yaml_content)

        elif msg_type == 'action':
            action_id = msg.get('action', '')
            if self.game and hasattr(self.game, 'execute_action'):
                success = self.game.execute_action(action_id)
                self._send_to_js('action_result', {
                    'action': action_id,
                    'success': success,
                })

        elif msg_type == 'pause':
            # TODO: Implement pause
            pass

        elif msg_type == 'resume':
            # TODO: Implement resume
            pass

    def _apply_level_yaml(self, yaml_content: str):
        """
        Apply level configuration from YAML string.
        Used by the level authoring tool for live preview.
        """
        if not self.game:
            self._send_to_js('level_error', {'error': 'No game loaded'})
            return

        try:
            import yaml
            level_data = yaml.safe_load(yaml_content)

            if not level_data:
                self._send_to_js('level_error', {'error': 'Empty YAML'})
                return

            # Use the game's level loader to parse the data
            if hasattr(self.game, '_level_loader') and self.game._level_loader:
                from pathlib import Path
                parsed = self.game._level_loader._parse_level_data(level_data, Path("preview.yaml"))
                self.game._apply_level_config(parsed)

                # Trigger level transition to reinitialize
                if hasattr(self.game, '_on_level_transition'):
                    self.game._on_level_transition()

                self._send_to_js('level_applied', {'success': True})
            else:
                self._send_to_js('level_error', {'error': 'Game does not support level loading'})

        except Exception as e:
            self._send_to_js('level_error', {'error': str(e)})

    # =========================================================================
    # IDE Bridge Integration
    # =========================================================================

    def _init_ide_bridge(self):
        """Initialize the IDE bridge for Monaco editor integration."""
        if sys.platform != "emscripten":
            return

        js_log("[BrowserGameRuntime] Initializing IDE bridge...")
        try:
            from ams.content_fs_browser import get_content_fs
            from ide_bridge import init_bridge

            content_fs = get_content_fs()
            self._ide_bridge = init_bridge(content_fs, self._ide_reload_callback)
            js_log(f"[BrowserGameRuntime] IDE bridge initialized, project path: {self._ide_bridge.get_project_path()}")

            # Load ide_bridge.js
            browser_platform.window.eval('''
                (function() {
                    if (window.ideBridge) {
                        console.log('[IDE Bridge] Already loaded');
                        return;
                    }
                    var script = document.createElement('script');
                    script.src = 'ide_bridge.js';
                    script.onload = function() {
                        console.log('[IDE Bridge] Script loaded');
                    };
                    script.onerror = function(e) {
                        console.error('[IDE Bridge] Failed to load:', e);
                    };
                    document.head.appendChild(script);
                })();
            ''')
        except Exception as e:
            js_log(f"[BrowserGameRuntime] IDE bridge init failed: {e}")

    def _ide_reload_callback(self):
        """Called by IDE bridge after files are updated to reload the game."""
        js_log("[BrowserGameRuntime] IDE reload callback triggered")
        if self._ide_bridge:
            # Load game from IDE project directory
            asyncio.create_task(self._load_ide_project())

    async def _load_ide_project(self):
        """Load game from IDE project files."""
        if not self._ide_bridge:
            return

        js_log("[BrowserGameRuntime] Loading IDE project...")
        try:
            project_path = self._ide_bridge.get_project_path()
            game_json_path = f"{project_path}/game.json"

            import os
            if os.path.exists(game_json_path):
                from ams.games.game_engine import GameEngine

                # Load game engine from project's game.json
                game_class = GameEngine.from_yaml(game_json_path)
                self.game = game_class.create_game(self.width, self.height)
                self._ide_mode = True
                js_log(f"[BrowserGameRuntime] IDE project loaded successfully")

                # Notify JS
                if sys.platform == "emscripten":
                    browser_platform.window.ideBridge.notifyReloaded()
            else:
                js_log(f"[BrowserGameRuntime] No game.json found at {game_json_path}")

        except Exception as e:
            js_log(f"[BrowserGameRuntime] IDE project load error: {e}")
            if sys.platform == "emscripten":
                browser_platform.window.ideBridge.notifyError(str(e), None, None)

    async def _process_ide_messages(self):
        """Process pending messages from IDE bridge."""
        if sys.platform != "emscripten":
            return

        if not hasattr(browser_platform.window, 'ideBridge'):
            return

        try:
            # Check for pending IDE messages
            if browser_platform.window.ideBridge.hasPendingMessages():
                msg = browser_platform.window.ideBridge.getNextMessage()
                if msg:
                    await self._handle_ide_message(msg)
        except Exception as e:
            js_log(f"[BrowserGameRuntime] IDE message processing error: {e}")

    async def _handle_ide_message(self, msg):
        """Handle a message from the IDE."""
        msg_type = msg.get('type', '')
        js_log(f"[BrowserGameRuntime] IDE message: {msg_type}")

        if msg_type == 'files':
            # Write files to ContentFS
            files = msg.get('files', {})
            if files and self._ide_bridge:
                import json
                result = self._ide_bridge.receive_files(json.dumps(files))
                js_log(f"[BrowserGameRuntime] Files written: {result}")

                # Notify JS
                if sys.platform == "emscripten":
                    files_written = result.get('files_written', 0) if isinstance(result, dict) else 0
                    browser_platform.window.ideBridge.notifyFilesReceived(files_written)

        elif msg_type == 'reload':
            # Trigger game reload
            await self._load_ide_project()

    def _broadcast_game_state(self):
        """Send current game state to JavaScript."""
        if not self.game:
            return

        state = {
            'game': self.game_slug,
            'game_name': self.game.NAME,
            'state': self.game.state.value if hasattr(self.game.state, 'value') else str(self.game.state),
            'score': self.game.get_score(),
        }

        # Add level info if available
        if hasattr(self.game, 'current_level_name'):
            state['level_name'] = self.game.current_level_name
        if hasattr(self.game, 'current_level_slug'):
            state['level_slug'] = self.game.current_level_slug

        # Add available actions
        if hasattr(self.game, 'get_available_actions'):
            state['actions'] = self.game.get_available_actions()

        # Add level group progress
        if hasattr(self.game, '_current_group') and self.game._current_group:
            group = self.game._current_group
            state['group'] = {
                'name': group.name,
                'progress': group.progress,
                'current_index': group.current_index,
                'total_levels': len(group.levels),
                'is_complete': group.is_complete,
            }

        self._send_to_js('game_state', state)

    def _send_to_js(self, event_type: str, data: dict):
        """
        Send a message to the parent JavaScript frame.

        Uses window.parent.postMessage for iframe communication.
        """
        if sys.platform != "emscripten":
            # In development, just log
            # print(f"[JS Bridge] {event_type}: {data}")
            return

        try:
            message = json.dumps({
                'source': 'ams_game',
                'type': event_type,
                'data': data,
            })
            browser_platform.window.parent.postMessage(message, '*')
        except Exception:
            pass

    def _render_loading_screen(self):
        """Render a loading screen when no game is loaded."""
        self.screen.fill((26, 26, 46))  # Dark blue background

        font = pygame.font.Font(None, 48)

        if self._load_error:
            # Show error in red
            error_font = pygame.font.Font(None, 32)
            title = font.render("Error Loading Game", True, (255, 80, 80))
            title_rect = title.get_rect(center=(self.width // 2, self.height // 2 - 40))
            self.screen.blit(title, title_rect)

            # Wrap error text
            error_text = error_font.render(self._load_error[:80], True, (255, 150, 150))
            error_rect = error_text.get_rect(center=(self.width // 2, self.height // 2 + 20))
            self.screen.blit(error_text, error_rect)
        else:
            text = font.render("Loading...", True, (0, 217, 255))
            rect = text.get_rect(center=(self.width // 2, self.height // 2))
            self.screen.blit(text, rect)

    def _process_lua_results(self):
        """Process results from WASMOON Lua execution."""
        if sys.platform != "emscripten":
            return

        try:
            if not hasattr(browser_platform.window, 'luaResponses'):
                return

            responses = browser_platform.window.luaResponses
            count = len(responses)
            if count > 0:
                # Log first few batches to verify flow
                if hasattr(self, '_lua_result_count'):
                    self._lua_result_count += count
                else:
                    self._lua_result_count = count
                if self._lua_result_count <= 10:
                    js_log(f"[Runtime] Processing {count} Lua responses (total: {self._lua_result_count})")
            while len(responses) > 0:
                resp_str = responses.pop(0)
                try:
                    resp = json.loads(resp_str)
                    self._apply_lua_result(resp)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            js_log(f"[BrowserGameRuntime] Error processing Lua results: {e}")

    def _apply_lua_result(self, result: dict):
        """Apply a Lua execution result to the game state."""
        result_type = result.get('type', '')
        data = result.get('data', {})

        # Handle Lua VM crash - stop the game loop
        if result_type == 'lua_crashed':
            error = data.get('error', 'Unknown error')
            context = data.get('context', 'Unknown')
            js_log(f"[BrowserGameRuntime] FATAL: Lua VM crashed in {context}: {error}")
            js_log("[BrowserGameRuntime] Stopping game loop due to Lua crash")
            self.running = False
            return

        if not self.game:
            return

        # Check if game has a behavior engine (YAML games)
        if not hasattr(self.game, '_behavior_engine'):
            return

        engine = self.game._behavior_engine

        # Check if it's a LuaEngineBrowser (has apply_lua_results)
        if hasattr(engine, 'apply_lua_results'):
            # Log occasionally to verify results are being applied
            entity_changes = data.get('entities', {}) if data else {}
            if entity_changes and engine.elapsed_time < 2.0:
                js_log(f"[Runtime] Applying Lua results: {len(entity_changes)} entity changes")
            engine.apply_lua_results(data)


def inject_fengari_scripts():
    """Inject Fengari and IDE bridge scripts into the page (called once at startup)."""
    if sys.platform != "emscripten":
        return

    js_log("[BrowserGameRuntime] Injecting Fengari and IDE bridge scripts...")

    try:
        # Initialize response arrays
        browser_platform.window.eval('''
            if (!window.gameMessages) window.gameMessages = [];
            if (!window.luaResponses) window.luaResponses = [];
        ''')

        # Load IDE bridge (for communication with Monaco editor)
        browser_platform.window.eval('''
            (function() {
                if (window.ideBridge) {
                    console.log('[IDE] Bridge already loaded');
                    return;
                }

                var bridge = document.createElement('script');
                bridge.src = 'ide_bridge.js';
                bridge.onload = function() {
                    console.log('[IDE] Bridge script loaded');
                };
                bridge.onerror = function(e) {
                    console.error('[IDE] Failed to load bridge:', e);
                };
                document.head.appendChild(bridge);
            })();
        ''')

        # Load Fengari bridge (will load fengari-web library itself)
        browser_platform.window.eval('''
            (function() {
                if (window.fengariBridge) {
                    console.log('[FENGARI] Already loaded');
                    return;
                }

                // Load our bridge which handles fengari loading
                var bridge = document.createElement('script');
                bridge.src = 'fengari_bridge.js';
                bridge.onload = function() {
                    console.log('[FENGARI] Bridge script loaded');
                };
                bridge.onerror = function(e) {
                    console.error('[FENGARI] Failed to load bridge:', e);
                };
                document.head.appendChild(bridge);
            })();
        ''')

        js_log("[BrowserGameRuntime] Fengari script injection initiated")
    except Exception as e:
        js_log(f"[BrowserGameRuntime] Error injecting Fengari: {e}")


# Keep old name for backwards compatibility
inject_wasmoon_scripts = inject_fengari_scripts
