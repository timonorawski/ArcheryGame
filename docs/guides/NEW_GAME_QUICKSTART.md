# New Game Quickstart Guide

This guide walks you through creating a new game for the AMS platform. Games are auto-discovered by the registry when they inherit from `BaseGame`.

## Quick Start

### 1. Create Game Directory

```bash
mkdir -p games/MyGame/input/sources
```

### 2. Set Up Input Abstraction

Create re-export files to use the common input module:

**games/MyGame/input/__init__.py:**
```python
"""MyGame Input Module - Re-exports from common input module."""
from games.common.input import InputEvent, InputManager
from games.common.input.sources import InputSource, MouseInputSource

__all__ = ['InputEvent', 'InputManager', 'InputSource', 'MouseInputSource']
```

**games/MyGame/input/input_manager.py:**
```python
"""MyGame Input Manager - Re-export from common module."""
from games.common.input.input_manager import InputManager

__all__ = ['InputManager']
```

**games/MyGame/input/input_event.py:**
```python
"""MyGame Input Event - Re-export from common module."""
from games.common.input.input_event import InputEvent

__all__ = ['InputEvent']
```

**games/MyGame/input/sources/__init__.py:**
```python
"""MyGame Input Sources - Re-export from common module."""
from games.common.input.sources import InputSource, MouseInputSource

__all__ = ['InputSource', 'MouseInputSource']
```

**games/MyGame/input/sources/mouse.py:**
```python
"""MyGame Mouse Input Source - Re-export from common module."""
from games.common.input.sources.mouse import MouseInputSource

__all__ = ['MouseInputSource']
```

### 3. Create game_mode.py (The Game Class)

**This is the key file.** Your game class inherits from `BaseGame` and declares all metadata as class attributes:

```python
"""MyGame - A fun target game."""
from typing import List, Optional, Tuple

import pygame

from games.common import BaseGame, GameState


class MyGameMode(BaseGame):
    """My awesome game.

    Inherits from BaseGame which provides:
    - Automatic state management (state property)
    - Palette support (_palette, cycle_palette, set_palette)
    - Quiver/ammo support (_quiver, _use_shot, _start_retrieval, etc.)
    - Base CLI arguments (--palette, --quiver-size, --retrieval-pause)
    """

    # =========================================================================
    # Game Metadata (used by registry for auto-discovery)
    # =========================================================================

    NAME = "My Game"
    DESCRIPTION = "A short description of my game."
    VERSION = "1.0.0"
    AUTHOR = "Your Name"

    # Game-specific CLI arguments (base args added automatically)
    ARGUMENTS = [
        {
            'name': '--difficulty',
            'type': str,
            'default': 'normal',
            'choices': ['easy', 'normal', 'hard'],
            'help': 'Game difficulty level'
        },
        {
            'name': '--time-limit',
            'type': int,
            'default': 60,
            'help': 'Time limit in seconds (0=unlimited)'
        },
    ]

    # =========================================================================
    # Initialization
    # =========================================================================

    def __init__(
        self,
        difficulty: str = 'normal',
        time_limit: int = 60,
        **kwargs,  # Pass palette, quiver args to BaseGame
    ):
        # IMPORTANT: Call super().__init__ to set up palette and quiver
        super().__init__(**kwargs)

        # Game-specific initialization
        self._difficulty = difficulty
        self._time_limit = time_limit
        self._score = 0
        self._game_over = False

    # =========================================================================
    # Required: Internal State (override from BaseGame)
    # =========================================================================

    def _get_internal_state(self) -> GameState:
        """Map internal state to standard GameState.

        BaseGame.state property calls this and handles RETRIEVAL automatically.
        """
        if self._game_over:
            return GameState.GAME_OVER
        return GameState.PLAYING

    # =========================================================================
    # Required: Game Interface
    # =========================================================================

    def get_score(self) -> int:
        """Return current score."""
        return self._score

    def handle_input(self, events: List) -> None:
        """Process input events (clicks/hits)."""
        for event in events:
            x, y = event.position.x, event.position.y
            # Handle the input at (x, y)
            # Example: check if hit a target, update score, etc.

    def update(self, dt: float) -> None:
        """Update game logic. dt is seconds since last frame."""
        # Update game state, timers, entities, etc.
        pass

    def render(self, screen: pygame.Surface) -> None:
        """Draw game to screen."""
        # Use self._palette for CV-compatible colors
        bg_color = self._palette.get_background_color()
        screen.fill(bg_color)

        # Draw your game elements
        # target_color = self._palette.get_target_color(index)
        # ui_color = self._palette.get_ui_color()
```

### 4. Create game_info.py (Factory Function)

The factory function bridges CLI args to your game class:

```python
"""MyGame - Game Info"""


def get_game_mode(**kwargs):
    """Factory function to create game instance.

    The registry calls this with CLI arguments.
    """
    from games.MyGame.game_mode import MyGameMode
    return MyGameMode(**kwargs)
```

**Note:** With BaseGame, metadata (NAME, DESCRIPTION, etc.) and ARGUMENTS come from the class itself. The game_info.py only needs the factory function.

### 5. Create Supporting Files

**games/MyGame/__init__.py:**
```python
"""MyGame package."""
```

**games/MyGame/config.py:**
```python
"""Configuration for MyGame."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from game directory
_env_path = Path(__file__).parent / '.env'
load_dotenv(_env_path)

def _get_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))

# Display settings (set by registry before game creation)
SCREEN_WIDTH = _get_int('SCREEN_WIDTH', 1280)
SCREEN_HEIGHT = _get_int('SCREEN_HEIGHT', 720)

# Add your game-specific settings here
```

**games/MyGame/.env:**
```env
# MyGame Configuration
SCREEN_WIDTH=1280
SCREEN_HEIGHT=720
```

## Running Your Game

### Development Mode (Recommended)
```bash
# List all games and their options
python dev_game.py --list

# See game-specific options
python dev_game.py mygame --help

# Play with options
python dev_game.py mygame --difficulty hard --time-limit 120
```

### With AMS (Production)
```bash
# Play with mouse backend
python ams_game.py --game mygame --backend mouse

# Play with laser pointer
python ams_game.py --game mygame --backend laser --fullscreen
```

## BaseGame Reference

### Class Attributes (Metadata)

| Attribute | Type | Description |
|-----------|------|-------------|
| `NAME` | str | Display name |
| `DESCRIPTION` | str | Short description |
| `VERSION` | str | Semantic version |
| `AUTHOR` | str | Author/team |
| `ARGUMENTS` | list | CLI argument definitions |

### Base Arguments (Automatic)

These are automatically available to all games via `BaseGame._BASE_ARGUMENTS`:

| Argument | Type | Description |
|----------|------|-------------|
| `--palette` | str | Test palette name |
| `--quiver-size` | int | Shots before retrieval |
| `--retrieval-pause` | int | Seconds for retrieval |

### Required Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `_get_internal_state()` | `-> GameState` | Map to standard state |
| `get_score()` | `-> int` | Current score |
| `handle_input(events)` | `(List) -> None` | Process inputs |
| `update(dt)` | `(float) -> None` | Update logic |
| `render(screen)` | `(Surface) -> None` | Draw game |

### Built-in Features

**Palette Support:**
```python
# In render():
bg = self._palette.get_background_color()
color = self._palette.get_target_color(0)
ui = self._palette.get_ui_color()

# Standalone testing:
self.cycle_palette()  # Returns new palette name
self.set_palette('bw')
```

**Quiver/Ammo Support:**
```python
# In handle_input():
if self._use_shot():  # Returns True when empty
    self._start_retrieval()

# In update():
if self._in_retrieval:
    if self._update_retrieval(dt):  # Returns True when done
        self._end_retrieval()

# Display:
remaining = self.shots_remaining  # None if unlimited
```

### GameState Enum

```python
from games.common import GameState

class GameState(Enum):
    PLAYING = "playing"      # Active gameplay
    PAUSED = "paused"        # Game paused
    RETRIEVAL = "retrieval"  # Retrieving ammo
    GAME_OVER = "game_over"  # Loss condition
    WON = "won"              # Win condition
```

### Internal State Pattern

For complex state machines, use a private enum:

```python
from enum import Enum, auto
from games.common import BaseGame, GameState


class _InternalState(Enum):
    WAITING = auto()
    PLAYING = auto()
    ROUND_OVER = auto()
    COMPLETE = auto()


class MyGameMode(BaseGame):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._internal_state = _InternalState.WAITING

    def _get_internal_state(self) -> GameState:
        mapping = {
            _InternalState.WAITING: GameState.PLAYING,
            _InternalState.PLAYING: GameState.PLAYING,
            _InternalState.ROUND_OVER: GameState.GAME_OVER,
            _InternalState.COMPLETE: GameState.WON,
        }
        return mapping[self._internal_state]
```

## CLI Arguments Format

```python
ARGUMENTS = [
    {
        'name': '--my-option',      # CLI flag (required)
        'type': str,                # str, int, float (required)
        'default': 'value',         # Default value (required)
        'help': 'Description',      # Help text (required)
        'choices': ['a', 'b'],      # Optional: valid values
    },
    {
        'name': '--flag',
        'action': 'store_true',     # For boolean flags
        'default': False,
        'help': 'Enable feature',
    },
]
```

## Multi-Device Design

### Pacing Presets

All games should support `--pacing` for device speed:

```python
ARGUMENTS = [
    {
        'name': '--pacing',
        'type': str,
        'default': 'throwing',
        'choices': ['archery', 'throwing', 'blaster'],
        'help': 'Device speed preset'
    },
]
```

| Preset | Cycle Time | Use Case |
|--------|------------|----------|
| archery | 3-8s | Bows, slow throwing |
| throwing | 1-2s | Darts, balls |
| blaster | 0.3s | Nerf, laser |

### Design Questions

1. **Does timing scale?** Can an archer complete the core loop?
2. **Is ammo considered?** What happens when arrows run out?
3. **Are pauses handled?** Retrieval shouldn't end the game
4. **Do combos work?** 8+ second windows for archery

## Example Games

| Game | Notable Features |
|------|------------------|
| BalloonPop | Simple BaseGame example |
| Containment | Physics, geometry, tempo presets |
| Grouping | Endless mode, precision training |
| ManyTargets | Complex internal states |
| FruitSlice | Arcing targets, bombs |
| GrowingTargets | Score-vs-difficulty tradeoff |
| DuckHunt | Multiple modes, trajectories |

## Troubleshooting

### Game not discovered
- Ensure `game_mode.py` has a class inheriting from `BaseGame`
- Check for import errors: `python -c "from games.MyGame.game_mode import *"`

### Arguments not showing
- Verify `ARGUMENTS` is a class attribute (not instance)
- Check format matches the examples above

### State not updating
- Ensure `_get_internal_state()` returns correct `GameState`
- BaseGame handles RETRIEVAL automatically
