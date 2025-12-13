"""
Level Bridge - JS/Python Communication for Level Authoring

Provides bidirectional communication between the browser game runtime
and JavaScript for level authoring features:
- Receive level YAML from editor
- Send validation results back
- Notify of game state changes
"""
import json
import sys
from typing import Callable, Optional, Any

from ams.yaml import loads as yaml_loads, YAMLNotAvailableError

# Conditional import for browser environment
if sys.platform == "emscripten":
    import platform as browser_platform


class LevelBridge:
    """
    Handles communication between Python game runtime and JavaScript.

    Used for:
    - Level authoring: Receive YAML, validate, apply
    - State sync: Send game state updates to UI
    - Commands: Receive play/pause/reset commands

    Communication uses window.postMessage for iframe isolation.
    """

    def __init__(self, on_level_yaml: Optional[Callable[[str], None]] = None):
        """
        Initialize the level bridge.

        Args:
            on_level_yaml: Callback when new YAML is received from editor
        """
        self._on_level_yaml = on_level_yaml
        self._message_handlers: dict[str, Callable] = {}
        self._setup_default_handlers()

    def _setup_default_handlers(self):
        """Register default message handlers."""
        self.register_handler('level_yaml', self._handle_level_yaml)
        self.register_handler('validate_yaml', self._handle_validate_yaml)

    def register_handler(self, msg_type: str, handler: Callable):
        """
        Register a handler for a message type.

        Args:
            msg_type: Message type to handle
            handler: Callback function(data: dict)
        """
        self._message_handlers[msg_type] = handler

    def process_message(self, message: dict) -> bool:
        """
        Process an incoming message from JavaScript.

        Args:
            message: Parsed message dict with 'type' and 'data' keys

        Returns:
            True if message was handled
        """
        msg_type = message.get('type', '')
        handler = self._message_handlers.get(msg_type)

        if handler:
            try:
                handler(message.get('data', {}))
                return True
            except Exception as e:
                self.send_error(f"Handler error for {msg_type}: {e}")
                return False

        return False

    def _handle_level_yaml(self, data: dict):
        """Handle level YAML from editor."""
        yaml_content = data.get('yaml', '')
        if self._on_level_yaml and yaml_content:
            self._on_level_yaml(yaml_content)

    def _handle_validate_yaml(self, data: dict):
        """Validate YAML without applying it."""
        yaml_content = data.get('yaml', '')
        game_type = data.get('game', 'containment')

        try:
            level_data = yaml_loads(yaml_content, format='yaml')

            if not level_data:
                self.send_validation_result(False, "Empty YAML content")
                return

            # Basic structure validation
            errors = self._validate_level_structure(level_data, game_type)

            if errors:
                self.send_validation_result(False, errors[0], errors)
            else:
                self.send_validation_result(True, "Valid level configuration")

        except YAMLNotAvailableError:
            self.send_validation_result(False, "YAML validation not available in browser. Use JSON format.")
        except Exception as e:
            self.send_validation_result(False, f"Validation error: {e}")

    def _validate_level_structure(self, data: dict, game_type: str) -> list[str]:
        """
        Validate level data structure for a game type.

        Args:
            data: Parsed level data
            game_type: Game identifier

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Common validations
        if not isinstance(data, dict):
            return ["Level must be a YAML mapping/object"]

        # Game-specific validations
        if game_type == 'containment':
            errors.extend(self._validate_containment_level(data))
        elif game_type == 'sweetphysics':
            errors.extend(self._validate_sweetphysics_level(data))

        return errors

    def _validate_containment_level(self, data: dict) -> list[str]:
        """Validate Containment level structure."""
        errors = []

        # Check hit_modes if present
        if 'hit_modes' in data:
            hit_modes = data['hit_modes']
            if not isinstance(hit_modes, dict):
                errors.append("hit_modes must be a mapping")
            else:
                valid_modes = {'deflector', 'spinner', 'point', 'connect', 'morph', 'grow'}
                for mode in hit_modes.get('enabled', []):
                    if mode not in valid_modes:
                        errors.append(f"Unknown hit mode: {mode}")

        # Check ball config if present
        if 'ball' in data:
            ball = data['ball']
            if not isinstance(ball, dict):
                errors.append("ball must be a mapping")
            else:
                if 'count' in ball and (not isinstance(ball['count'], int) or ball['count'] < 1):
                    errors.append("ball.count must be a positive integer")
                if 'radius' in ball and (not isinstance(ball['radius'], (int, float)) or ball['radius'] <= 0):
                    errors.append("ball.radius must be a positive number")

        # Check gaps if present
        if 'gaps' in data:
            gaps = data['gaps']
            if not isinstance(gaps, list):
                errors.append("gaps must be a list")
            else:
                for i, gap in enumerate(gaps):
                    if not isinstance(gap, dict):
                        errors.append(f"gaps[{i}] must be a mapping")
                    elif 'position' not in gap:
                        errors.append(f"gaps[{i}] missing required 'position' field")

        return errors

    def _validate_sweetphysics_level(self, data: dict) -> list[str]:
        """Validate SweetPhysics level structure."""
        errors = []

        # Check targets if present
        if 'targets' in data:
            targets = data['targets']
            if not isinstance(targets, list):
                errors.append("targets must be a list")
            else:
                valid_types = {'sweet', 'bomb', 'multiplier', 'time_bonus'}
                for i, target in enumerate(targets):
                    if not isinstance(target, dict):
                        errors.append(f"targets[{i}] must be a mapping")
                    elif 'type' in target and target['type'] not in valid_types:
                        errors.append(f"targets[{i}]: unknown type '{target['type']}'")

        # Check physics if present
        if 'physics' in data:
            physics = data['physics']
            if not isinstance(physics, dict):
                errors.append("physics must be a mapping")
            else:
                if 'gravity' in physics:
                    grav = physics['gravity']
                    if not isinstance(grav, (int, float, list)):
                        errors.append("physics.gravity must be a number or [x, y] list")

        return errors

    def send_validation_result(self, valid: bool, message: str, errors: Optional[list[str]] = None):
        """
        Send validation result to JavaScript.

        Args:
            valid: Whether validation passed
            message: Summary message
            errors: List of specific errors
        """
        self._send_to_js('validation_result', {
            'valid': valid,
            'message': message,
            'errors': errors or [],
        })

    def send_level_applied(self, level_name: str, success: bool = True):
        """
        Notify JavaScript that level was applied.

        Args:
            level_name: Name of the applied level
            success: Whether application succeeded
        """
        self._send_to_js('level_applied', {
            'name': level_name,
            'success': success,
        })

    def send_level_error(self, error: str):
        """
        Send level loading error to JavaScript.

        Args:
            error: Error message
        """
        self._send_to_js('level_error', {
            'error': error,
        })

    def send_game_state(self, state: dict):
        """
        Send current game state to JavaScript.

        Args:
            state: Game state dict
        """
        self._send_to_js('game_state', state)

    def send_error(self, error: str):
        """
        Send general error to JavaScript.

        Args:
            error: Error message
        """
        self._send_to_js('error', {
            'message': error,
        })

    def _send_to_js(self, event_type: str, data: dict):
        """
        Send a message to the parent JavaScript frame.

        Uses window.parent.postMessage for iframe communication.

        Args:
            event_type: Type of event
            data: Event data
        """
        if sys.platform != "emscripten":
            # In development, could log or use alternative communication
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


class LevelAuthoringSession:
    """
    Manages a level authoring session with live preview.

    Coordinates between:
    - YAML editor in JavaScript
    - Game runtime in Python
    - Validation feedback
    """

    def __init__(self, game, bridge: LevelBridge):
        """
        Initialize authoring session.

        Args:
            game: Game instance to preview levels
            bridge: LevelBridge for JS communication
        """
        self.game = game
        self.bridge = bridge
        self._last_valid_yaml: Optional[str] = None
        self._preview_mode = True

        # Register for YAML updates
        bridge._on_level_yaml = self._on_yaml_received

    def _on_yaml_received(self, yaml_content: str):
        """Handle new YAML from editor."""
        if not self.game:
            self.bridge.send_level_error("No game loaded for preview")
            return

        try:
            level_data = yaml_loads(yaml_content, format='yaml')

            if not level_data:
                self.bridge.send_level_error("Empty YAML")
                return

            # Use game's level loader if available
            if hasattr(self.game, '_level_loader') and self.game._level_loader:
                from pathlib import Path
                parsed = self.game._level_loader._parse_level_data(level_data, Path("preview.yaml"))
                self.game._apply_level_config(parsed)

                # Trigger level transition
                if hasattr(self.game, '_on_level_transition'):
                    self.game._on_level_transition()

                self._last_valid_yaml = yaml_content
                level_name = level_data.get('name', 'Preview')
                self.bridge.send_level_applied(level_name)
            else:
                self.bridge.send_level_error("Game does not support level loading")

        except YAMLNotAvailableError:
            self.bridge.send_level_error("YAML loading not available in browser. Use JSON format.")
        except Exception as e:
            self.bridge.send_level_error(f"Failed to apply level: {e}")

    def revert_to_last_valid(self):
        """Revert to the last valid level configuration."""
        if self._last_valid_yaml:
            self._on_yaml_received(self._last_valid_yaml)

    def get_current_yaml(self) -> Optional[str]:
        """Get the current valid YAML."""
        return self._last_valid_yaml
