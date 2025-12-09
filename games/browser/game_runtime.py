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

        # Signal ready to JS
        js_log("[BrowserGameRuntime] Sending ready signal...")
        self._send_ready_signal()
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
            from games.registry import GameRegistry
            registry = GameRegistry()
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

                # Let input adapter handle the event
                self.input_adapter.handle_pygame_event(event)

                # Let game handle raw pygame events if it needs to
                if self.game and hasattr(self.game, 'handle_pygame_event'):
                    self.game.handle_pygame_event(event)

            # Process messages from JavaScript
            await self._process_js_messages()

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
