# AMS Browser Deployment Plan

Deploy AMS pygame games to the browser via pygbag/pygame-wasm, enabling play, observation, and level authoring directly in the web interface.

## Overview

### Goals
1. **Play Mode**: Run Containment and SweetPhysics games directly in browser
2. **Observer Mode**: Watch live AMS sessions remotely (spectate projector view)
3. **Level Authoring**: YAML editor with live game preview for creating levels

### Technology Stack
- **[Pygbag](https://pygame-web.github.io/wiki/pygbag/)**: Compiles pygame to WebAssembly
- **Svelte**: Frontend framework (existing web controller)
- **FastAPI**: Backend server (existing)
- **Monaco Editor**: VS Code's editor for YAML authoring

### Architecture Decision: Hybrid Approach

| Use Case | Technology | Rationale |
|----------|------------|-----------|
| **Play Mode** | Pygbag (WASM) | Full client-side gameplay, zero latency, offline-capable |
| **Observer Mode** | Canvas streaming | Server renders actual AMS state, streams frames via WebSocket |
| **Level Authoring** | Pygbag + Monaco | Live WASM preview, server-side YAML validation |

---

## Current Architecture Summary

### Game Structure
All games inherit from `BaseGame` (`games/common/base_game.py`):

```python
class BaseGame(ABC):
    # Class attributes
    NAME: str
    DESCRIPTION: str
    LEVELS_DIR: Optional[Path]
    ARGUMENTS: List[Dict]

    # Abstract methods games must implement
    def handle_input(self, events: List[InputEvent]) -> None
    def update(self, dt: float) -> None
    def render(self, screen: pygame.Surface) -> None
    def get_score(self) -> int
    def _get_internal_state(self) -> GameState

    # Level support (optional)
    def _create_level_loader(self) -> LevelLoader
    def _apply_level_config(self, level_data) -> None
    def _on_level_transition(self) -> None
```

### Input Flow
```
Detection Layer (mouse/laser/object) → PlaneHitEvent (normalized [0,1])
         ↓
AMSInputAdapter → InputEvent (pixel coordinates)
         ↓
Games (handle_input receives InputEvent list)
```

Games are input-source agnostic - they receive `InputEvent` objects with `position: Vector2D` and `timestamp: float`.

### Existing Web Infrastructure
- **FastAPI server** (`ams/web_controller/server.py`) on port 8080
- **WebSocket** at `/ws` for real-time state sync
- **Svelte frontend** (`ams/web_controller/frontend/`) for mobile control
- **Commands**: `launch_game`, `pause`, `resume`, `game_action`, `set_backend`, etc.
- **State broadcast**: `GameState` and `SessionInfo` dataclasses

### Game Dependencies
| Game | Dependencies |
|------|--------------|
| Containment | pygame only (custom physics) |
| SweetPhysics | pygame + pymunk |

Note: [Pymunk works in pygbag](https://pmp-p.github.io/pygame-wasm/pygame.html?org.chipmunk6.pymunk04) (WASM demo exists).

---

## File Structure

### New Files to Create

```
games/browser/                          # Browser runtime
├── main.py                             # Pygbag entry point
├── game_runtime.py                     # Async game loop wrapper
├── input_adapter.py                    # Browser input → InputEvent
├── level_bridge.py                     # JS ↔ Python postMessage
├── platform_compat.py                  # Platform detection utilities
├── build.py                            # Build script
└── requirements.txt                    # Browser dependencies

ams/web_controller/
├── level_api.py                        # NEW: Level validation endpoints
├── observer.py                         # NEW: Frame streaming
└── frontend/src/
    ├── routes/
    │   ├── play/+page.svelte           # Play mode page
    │   ├── observe/+page.svelte        # Observer mode page
    │   └── author/+page.svelte         # Level authoring page
    └── lib/
        ├── GameCanvas.svelte           # Pygbag iframe wrapper
        ├── ObserverCanvas.svelte       # Frame stream viewer
        ├── LevelEditor.svelte          # Monaco YAML editor
        └── LevelPreview.svelte         # Live preview component
```

### Files to Modify

```
ams/web_controller/server.py            # Add observer endpoints, level API routes
ams/web_controller/frontend/package.json # Add Monaco dependency
```

### Build Output

```
ams/web_controller/frontend/dist/pygbag/
├── index.html                          # Pygbag loader
├── ams_games.wasm                      # Compiled Python + pygame
├── ams_games.data                      # Bundled assets (levels, etc.)
└── ams_games.js                        # Pygbag runtime
```

---

## Phase 1: Pygbag-Compatible Game Runtime

### 1.1 Entry Point (`games/browser/main.py`)

Pygbag requires an async main function:

```python
import asyncio
import sys
import pygame

async def main():
    pygame.init()

    # Parse URL parameters for game selection
    game_slug = get_url_param('game', 'containment')
    level_slug = get_url_param('level', None)

    # Create game via registry
    screen = pygame.display.set_mode((1280, 720))
    runtime = BrowserGameRuntime(screen)

    await runtime.load_game(game_slug, level=level_slug)
    await runtime.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### 1.2 Async Game Loop (`games/browser/game_runtime.py`)

```python
import asyncio
import sys
import pygame
from games.registry import GameRegistry

class BrowserGameRuntime:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.width = screen.get_width()
        self.height = screen.get_height()
        self.registry = GameRegistry()
        self.game = None
        self.input_adapter = BrowserInputAdapter(self.width, self.height)
        self.running = True

    async def load_game(self, game_slug: str, level: str = None, level_group: str = None):
        """Load a game by slug."""
        self.game = self.registry.create_game(
            game_slug,
            self.width,
            self.height,
            level=level,
            level_group=level_group,
        )

    async def run(self):
        """Main async game loop."""
        clock = pygame.time.Clock()

        while self.running:
            dt = clock.tick(60) / 1000.0

            # Process pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                self.input_adapter.handle_pygame_event(event)
                if hasattr(self.game, 'handle_pygame_event'):
                    self.game.handle_pygame_event(event)

            # Process JS bridge messages
            await self._process_js_messages()

            # Game loop
            input_events = self.input_adapter.get_events()
            self.game.handle_input(input_events)
            self.game.update(dt)
            self.game.render(self.screen)

            # Send state to JS
            self._send_state_to_js()

            pygame.display.flip()
            await asyncio.sleep(0)  # CRITICAL: Yield to browser event loop

    async def _process_js_messages(self):
        """Handle messages from JavaScript."""
        if sys.platform != "emscripten":
            return

        import platform
        # Check for pending messages from JS
        while hasattr(platform.window, 'gameMessages') and len(platform.window.gameMessages) > 0:
            msg = platform.window.gameMessages.pop(0)
            await self._handle_js_message(msg)

    async def _handle_js_message(self, msg: dict):
        """Process a single message from JS."""
        msg_type = msg.get('type')

        if msg_type == 'load_level':
            # Load level from YAML string
            yaml_content = msg.get('yaml')
            self._apply_level_yaml(yaml_content)

        elif msg_type == 'load_game':
            game_slug = msg.get('game')
            level = msg.get('level')
            await self.load_game(game_slug, level=level)

        elif msg_type == 'action':
            action_id = msg.get('action')
            if hasattr(self.game, 'execute_action'):
                self.game.execute_action(action_id)

    def _apply_level_yaml(self, yaml_content: str):
        """Apply level from YAML string (for authoring)."""
        import yaml
        try:
            level_data = yaml.safe_load(yaml_content)
            if hasattr(self.game, '_apply_level_config'):
                # Use game's level loader to parse
                loader = self.game._level_loader
                if loader:
                    parsed = loader._parse_level_data(level_data, None)
                    self.game._apply_level_config(parsed)
                    self.game._on_level_transition()
            self._send_to_js('level_applied', {'success': True})
        except Exception as e:
            self._send_to_js('level_error', {'error': str(e)})

    def _send_state_to_js(self):
        """Send game state to JavaScript parent."""
        if sys.platform != "emscripten":
            return

        state = {
            'game_name': self.game.NAME,
            'state': self.game.state.value,
            'score': self.game.get_score(),
            'level': self.game.current_level_name if hasattr(self.game, 'current_level_name') else '',
        }

        if hasattr(self.game, 'get_available_actions'):
            state['actions'] = self.game.get_available_actions()

        self._send_to_js('game_state', state)

    def _send_to_js(self, event_type: str, data: dict):
        """Send message to JavaScript."""
        if sys.platform != "emscripten":
            return

        import platform
        import json
        platform.window.postMessage(json.dumps({
            'type': event_type,
            'data': data
        }), '*')
```

### 1.3 Browser Input Adapter (`games/browser/input_adapter.py`)

```python
import time
import pygame
from typing import List
from models import Vector2D
from games.common.input import InputEvent, EventType

class BrowserInputAdapter:
    """Convert browser/pygame events to InputEvent objects."""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._events: List[InputEvent] = []

    def handle_pygame_event(self, event: pygame.event.Event):
        """Process a pygame event."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._add_hit(event.pos)
        elif event.type == pygame.FINGERDOWN:
            # Touch events have normalized coordinates
            x = int(event.x * self.screen_width)
            y = int(event.y * self.screen_height)
            self._add_hit((x, y))

    def _add_hit(self, pos: tuple):
        """Add a hit event."""
        self._events.append(InputEvent(
            position=Vector2D(x=pos[0], y=pos[1]),
            timestamp=time.monotonic(),
            event_type=EventType.HIT
        ))

    def get_events(self) -> List[InputEvent]:
        """Get and clear pending events."""
        events = self._events[:]
        self._events.clear()
        return events

    def update(self, dt: float):
        """Update method (for InputSource compatibility)."""
        pass
```

### 1.4 Platform Compatibility (`games/browser/platform_compat.py`)

```python
import sys

def is_browser() -> bool:
    """Check if running in browser (Emscripten/WASM)."""
    return sys.platform == "emscripten"

def get_url_param(name: str, default: str = None) -> str:
    """Get URL parameter value."""
    if not is_browser():
        return default

    import platform
    params = platform.window.location.search
    # Parse ?game=foo&level=bar
    if params.startswith('?'):
        for param in params[1:].split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                if key == name:
                    return value
    return default

async def load_file_async(path: str) -> str:
    """Load file content, async in browser."""
    if is_browser():
        import platform
        async with platform.fopen(path, 'r') as f:
            return f.read()
    else:
        with open(path, 'r') as f:
            return f.read()
```

### 1.5 Level Loading Adaptation

Modify level loaders to support async loading in browser. Add to `games/common/levels.py`:

```python
# At module level
import sys

async def load_yaml_async(path: Path) -> dict:
    """Load YAML file, async-compatible."""
    if sys.platform == "emscripten":
        import platform
        async with platform.fopen(str(path), 'r') as f:
            content = f.read()
        return yaml.safe_load(content)
    else:
        with open(path, 'r') as f:
            return yaml.safe_load(f)
```

---

## Phase 2: Build System

### 2.1 Build Script (`games/browser/build.py`)

```python
#!/usr/bin/env python3
"""Build script for pygbag deployment."""
import subprocess
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BROWSER_DIR = PROJECT_ROOT / "games" / "browser"
OUTPUT_DIR = PROJECT_ROOT / "ams" / "web_controller" / "frontend" / "dist" / "pygbag"

def build():
    """Build the pygbag package."""
    # Clean output
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # Run pygbag build
    subprocess.run([
        "python3", "-m", "pygbag",
        "--build",
        "--app_name", "ams_games",
        "--template", "default",
        str(BROWSER_DIR / "main.py")
    ], check=True)

    # Copy output to web controller
    build_output = BROWSER_DIR / "build" / "web"
    if build_output.exists():
        shutil.copytree(build_output, OUTPUT_DIR, dirs_exist_ok=True)

    print(f"Build complete: {OUTPUT_DIR}")

if __name__ == "__main__":
    build()
```

### 2.2 Browser Requirements (`games/browser/requirements.txt`)

```
pygame-ce>=2.4.0
pymunk>=6.6.0
pyyaml>=6.0
pydantic>=2.0
```

### 2.3 Asset Bundling

Pygbag bundles files in the `games/browser/` directory. Symlink or copy levels:

```python
# In build.py, add:
def bundle_assets():
    """Bundle game assets into browser directory."""
    assets_dir = BROWSER_DIR / "assets"
    assets_dir.mkdir(exist_ok=True)

    # Copy level files
    for game in ["SweetPhysics", "Containment"]:
        levels_src = PROJECT_ROOT / "games" / game / "levels"
        levels_dst = assets_dir / game.lower() / "levels"
        if levels_src.exists():
            shutil.copytree(levels_src, levels_dst, dirs_exist_ok=True)
```

---

## Phase 3: Svelte Frontend Integration

### 3.1 GameCanvas Component (`frontend/src/lib/GameCanvas.svelte`)

```svelte
<script>
    import { onMount, onDestroy, createEventDispatcher } from 'svelte';

    export let game = 'containment';
    export let level = null;
    export let levelGroup = null;
    export let levelYaml = null;  // For authoring mode - YAML string to load

    const dispatch = createEventDispatcher();

    let iframe;
    let ready = false;

    // Build URL with parameters
    $: iframeSrc = buildUrl(game, level, levelGroup);

    function buildUrl(game, level, levelGroup) {
        let url = '/pygbag/index.html';
        const params = new URLSearchParams();
        if (game) params.set('game', game);
        if (level) params.set('level', level);
        if (levelGroup) params.set('level_group', levelGroup);
        const qs = params.toString();
        return qs ? `${url}?${qs}` : url;
    }

    function sendToGame(message) {
        if (iframe?.contentWindow && ready) {
            iframe.contentWindow.postMessage(JSON.stringify(message), '*');
        }
    }

    // When levelYaml changes (authoring mode), send to game
    $: if (levelYaml && ready) {
        sendToGame({ type: 'load_level', yaml: levelYaml });
    }

    function handleMessage(event) {
        try {
            const data = JSON.parse(event.data);

            if (data.type === 'ready') {
                ready = true;
                dispatch('ready');
            } else if (data.type === 'game_state') {
                dispatch('stateChange', data.data);
            } else if (data.type === 'level_applied') {
                dispatch('levelApplied', data.data);
            } else if (data.type === 'level_error') {
                dispatch('levelError', data.data);
            }
        } catch (e) {
            // Not a JSON message, ignore
        }
    }

    onMount(() => {
        window.addEventListener('message', handleMessage);
    });

    onDestroy(() => {
        window.removeEventListener('message', handleMessage);
    });

    // Expose method to parent
    export function executeAction(actionId) {
        sendToGame({ type: 'action', action: actionId });
    }

    export function loadGame(gameSlug, levelSlug = null) {
        sendToGame({ type: 'load_game', game: gameSlug, level: levelSlug });
    }
</script>

<div class="game-canvas-container">
    {#if !ready}
        <div class="loading">Loading game...</div>
    {/if}
    <iframe
        bind:this={iframe}
        src={iframeSrc}
        title="AMS Game"
        class="game-iframe"
        class:hidden={!ready}
        allow="autoplay"
    />
</div>

<style>
    .game-canvas-container {
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 9;
        background: #1a1a2e;
        border-radius: 8px;
        overflow: hidden;
    }

    .game-iframe {
        width: 100%;
        height: 100%;
        border: none;
    }

    .game-iframe.hidden {
        visibility: hidden;
    }

    .loading {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        color: #00d9ff;
        font-size: 18px;
    }
</style>
```

### 3.2 Play Mode Page (`frontend/src/routes/play/+page.svelte`)

```svelte
<script>
    import GameCanvas from '$lib/GameCanvas.svelte';
    import GameSelector from '$lib/GameSelector.svelte';

    let selectedGame = null;
    let selectedLevel = null;
    let gameState = null;
    let gameCanvas;

    function handleGameSelect(event) {
        selectedGame = event.detail.game;
        selectedLevel = event.detail.level;
    }

    function handleStateChange(event) {
        gameState = event.detail;
    }

    function handleAction(actionId) {
        gameCanvas?.executeAction(actionId);
    }

    function backToSelection() {
        selectedGame = null;
        selectedLevel = null;
        gameState = null;
    }
</script>

<main>
    <header>
        <h1>AMS Games</h1>
        {#if selectedGame}
            <button on:click={backToSelection}>← Back</button>
        {/if}
    </header>

    {#if !selectedGame}
        <GameSelector on:select={handleGameSelect} />
    {:else}
        <div class="game-view">
            <GameCanvas
                bind:this={gameCanvas}
                game={selectedGame}
                level={selectedLevel}
                on:stateChange={handleStateChange}
            />

            {#if gameState}
                <div class="game-info">
                    <div class="score">Score: {gameState.score}</div>
                    <div class="state">{gameState.state}</div>

                    {#if gameState.actions?.length}
                        <div class="actions">
                            {#each gameState.actions as action}
                                <button
                                    class="action-btn {action.style}"
                                    on:click={() => handleAction(action.id)}
                                >
                                    {action.label}
                                </button>
                            {/each}
                        </div>
                    {/if}
                </div>
            {/if}
        </div>
    {/if}
</main>

<style>
    main {
        padding: 16px;
        max-width: 1200px;
        margin: 0 auto;
    }

    header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }

    h1 {
        color: #00d9ff;
        margin: 0;
    }

    .game-view {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .game-info {
        display: flex;
        gap: 16px;
        align-items: center;
        flex-wrap: wrap;
    }

    .score {
        font-size: 24px;
        color: #00d9ff;
    }

    .actions {
        display: flex;
        gap: 8px;
    }

    .action-btn {
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }

    .action-btn.primary {
        background: #00d9ff;
        color: #000;
    }

    .action-btn.secondary {
        background: rgba(255,255,255,0.1);
        color: #ccc;
    }
</style>
```

### 3.3 Game Selector Component (`frontend/src/lib/GameSelector.svelte`)

```svelte
<script>
    import { onMount, createEventDispatcher } from 'svelte';

    const dispatch = createEventDispatcher();

    let games = [];
    let selectedGame = null;
    let levels = [];
    let groups = [];

    onMount(async () => {
        // Fetch available games from API
        const res = await fetch('/api/games');
        games = await res.json();
    });

    async function selectGame(game) {
        selectedGame = game;

        // Fetch levels for this game
        const res = await fetch(`/api/levels/${game.slug}`);
        const data = await res.json();
        levels = data.levels || [];
        groups = data.groups || [];
    }

    function launchGame(level = null, group = null) {
        dispatch('select', {
            game: selectedGame.slug,
            level: level,
            levelGroup: group
        });
    }
</script>

<div class="selector">
    {#if !selectedGame}
        <h2>Select a Game</h2>
        <div class="game-grid">
            {#each games as game}
                <button class="game-card" on:click={() => selectGame(game)}>
                    <h3>{game.name}</h3>
                    <p>{game.description}</p>
                </button>
            {/each}
        </div>
    {:else}
        <h2>{selectedGame.name}</h2>
        <p>{selectedGame.description}</p>

        <button class="play-btn primary" on:click={() => launchGame()}>
            Play (Default)
        </button>

        {#if groups.length > 0}
            <h3>Level Groups</h3>
            <div class="level-grid">
                {#each groups as group}
                    <button class="level-card" on:click={() => launchGame(null, group.slug)}>
                        <strong>{group.name}</strong>
                        <span>{group.levels?.length || 0} levels</span>
                    </button>
                {/each}
            </div>
        {/if}

        {#if levels.length > 0}
            <h3>Individual Levels</h3>
            <div class="level-grid">
                {#each levels as level}
                    <button class="level-card" on:click={() => launchGame(level.slug)}>
                        <strong>{level.name}</strong>
                        <span>{'★'.repeat(level.difficulty)}</span>
                    </button>
                {/each}
            </div>
        {/if}

        <button class="back-btn" on:click={() => selectedGame = null}>
            ← Back to Games
        </button>
    {/if}
</div>

<style>
    .selector {
        padding: 16px;
    }

    .game-grid, .level-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 16px;
        margin: 16px 0;
    }

    .game-card, .level-card {
        background: #16213e;
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 8px;
        padding: 16px;
        text-align: left;
        cursor: pointer;
        transition: border-color 0.2s;
    }

    .game-card:hover, .level-card:hover {
        border-color: #00d9ff;
    }

    .game-card h3 {
        color: #00d9ff;
        margin: 0 0 8px;
    }

    .game-card p {
        color: #888;
        margin: 0;
        font-size: 14px;
    }

    .play-btn {
        padding: 12px 24px;
        font-size: 18px;
        border: none;
        border-radius: 8px;
        cursor: pointer;
    }

    .play-btn.primary {
        background: #00d9ff;
        color: #000;
    }
</style>
```

---

## Phase 4: Observer Mode

### 4.1 Frame Streaming Endpoint (`ams/web_controller/observer.py`)

```python
"""Observer mode - stream game canvas to browser."""
import asyncio
import io
from typing import Optional

import pygame
from fastapi import WebSocket, WebSocketDisconnect
from PIL import Image

class ObserverStream:
    """Manages frame streaming to observer clients."""

    def __init__(self):
        self.clients: list[WebSocket] = []
        self.current_frame: Optional[bytes] = None
        self._running = False

    async def connect(self, websocket: WebSocket):
        """Add a new observer client."""
        await websocket.accept()
        self.clients.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove an observer client."""
        if websocket in self.clients:
            self.clients.remove(websocket)

    def capture_frame(self, screen: pygame.Surface) -> bytes:
        """Capture pygame surface as JPEG bytes."""
        # Convert pygame surface to PIL Image
        data = pygame.surfarray.array3d(screen)
        data = data.swapaxes(0, 1)  # pygame uses (width, height), PIL uses (height, width)

        img = Image.fromarray(data)

        # Compress to JPEG
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=70)
        return buffer.getvalue()

    async def broadcast_frame(self, frame: bytes):
        """Send frame to all connected observers."""
        self.current_frame = frame

        disconnected = []
        for client in self.clients:
            try:
                await client.send_bytes(frame)
            except Exception:
                disconnected.append(client)

        # Clean up disconnected clients
        for client in disconnected:
            self.disconnect(client)


# Singleton instance
observer_stream = ObserverStream()
```

### 4.2 Add Observer Endpoint to Server (`ams/web_controller/server.py`)

```python
from ams.web_controller.observer import observer_stream

@app.websocket("/ws/observer")
async def observer_websocket(websocket: WebSocket):
    """WebSocket endpoint for observer frame streaming."""
    await observer_stream.connect(websocket)
    try:
        while True:
            # Keep connection alive, frames sent by main loop
            await websocket.receive_text()
    except WebSocketDisconnect:
        observer_stream.disconnect(websocket)
```

### 4.3 Integrate with Game Loop (`ams/web_controller/ams_integration.py`)

Add frame capture to the render loop:

```python
# In update() method, after game.render(screen):
if observer_stream.clients:
    frame = observer_stream.capture_frame(self.screen)
    asyncio.create_task(observer_stream.broadcast_frame(frame))
```

### 4.4 Observer Canvas Component (`frontend/src/lib/ObserverCanvas.svelte`)

```svelte
<script>
    import { onMount, onDestroy, createEventDispatcher } from 'svelte';

    const dispatch = createEventDispatcher();

    let canvas;
    let ctx;
    let ws;
    let connected = false;

    onMount(() => {
        ctx = canvas.getContext('2d');
        connect();
    });

    onDestroy(() => {
        if (ws) ws.close();
    });

    function connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/ws/observer`);
        ws.binaryType = 'arraybuffer';

        ws.onopen = () => {
            connected = true;
            dispatch('connected');
        };

        ws.onclose = () => {
            connected = false;
            dispatch('disconnected');
            // Reconnect after delay
            setTimeout(connect, 2000);
        };

        ws.onmessage = (event) => {
            renderFrame(event.data);
        };
    }

    function renderFrame(data) {
        const blob = new Blob([data], { type: 'image/jpeg' });
        const url = URL.createObjectURL(blob);

        const img = new Image();
        img.onload = () => {
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(url);
        };
        img.src = url;
    }
</script>

<div class="observer-container">
    <canvas bind:this={canvas} width={1280} height={720} />

    {#if !connected}
        <div class="overlay">
            <div class="status">Connecting to AMS...</div>
        </div>
    {/if}
</div>

<style>
    .observer-container {
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 9;
        background: #000;
        border-radius: 8px;
        overflow: hidden;
    }

    canvas {
        width: 100%;
        height: 100%;
    }

    .overlay {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.8);
    }

    .status {
        color: #00d9ff;
        font-size: 18px;
    }
</style>
```

### 4.5 Observer Page (`frontend/src/routes/observe/+page.svelte`)

```svelte
<script>
    import ObserverCanvas from '$lib/ObserverCanvas.svelte';
    import GameState from '$lib/GameState.svelte';

    let connected = false;
    let gameState = null;

    // Also connect to regular WebSocket for state updates
    import { onMount } from 'svelte';

    let ws;

    onMount(() => {
        connectState();
    });

    function connectState() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'state') {
                gameState = data.game;
            }
        };

        ws.onclose = () => setTimeout(connectState, 2000);
    }
</script>

<main>
    <header>
        <h1>Observer Mode</h1>
        <span class="status" class:connected>
            {connected ? '● Connected' : '○ Connecting...'}
        </span>
    </header>

    <div class="observer-view">
        <ObserverCanvas
            on:connected={() => connected = true}
            on:disconnected={() => connected = false}
        />

        {#if gameState}
            <GameState {gameState} />
        {:else}
            <p class="waiting">Waiting for game to start...</p>
        {/if}
    </div>
</main>

<style>
    main {
        padding: 16px;
        max-width: 1200px;
        margin: 0 auto;
    }

    header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }

    h1 {
        color: #00d9ff;
        margin: 0;
    }

    .status {
        color: #888;
    }

    .status.connected {
        color: #0f0;
    }

    .observer-view {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .waiting {
        color: #888;
        text-align: center;
    }
</style>
```

---

## Phase 5: Level Authoring

### 5.1 Level Editor Component (`frontend/src/lib/LevelEditor.svelte`)

```svelte
<script>
    import { onMount, createEventDispatcher } from 'svelte';
    import * as monaco from 'monaco-editor';

    export let value = '';
    export let schema = null;
    export let readonly = false;

    const dispatch = createEventDispatcher();

    let container;
    let editor;
    let debounceTimer;

    onMount(() => {
        // Configure YAML language
        monaco.languages.register({ id: 'yaml' });

        editor = monaco.editor.create(container, {
            value,
            language: 'yaml',
            theme: 'vs-dark',
            minimap: { enabled: false },
            automaticLayout: true,
            readOnly: readonly,
            fontSize: 14,
            tabSize: 2,
        });

        // Set up validation if schema provided
        if (schema) {
            setupValidation(schema);
        }

        // Emit changes with debounce
        editor.onDidChangeModelContent(() => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                dispatch('change', { value: editor.getValue() });
            }, 300);
        });

        return () => {
            editor.dispose();
        };
    });

    function setupValidation(schema) {
        // Monaco YAML validation setup
        // Requires monaco-yaml package
    }

    export function setValue(newValue) {
        if (editor && newValue !== editor.getValue()) {
            editor.setValue(newValue);
        }
    }

    export function getValue() {
        return editor?.getValue() || '';
    }

    export function setError(line, message) {
        if (!editor) return;

        monaco.editor.setModelMarkers(editor.getModel(), 'validation', [{
            startLineNumber: line,
            startColumn: 1,
            endLineNumber: line,
            endColumn: 1000,
            message,
            severity: monaco.MarkerSeverity.Error
        }]);
    }

    export function clearErrors() {
        if (editor) {
            monaco.editor.setModelMarkers(editor.getModel(), 'validation', []);
        }
    }
</script>

<div class="editor-container" bind:this={container}></div>

<style>
    .editor-container {
        width: 100%;
        height: 100%;
        min-height: 400px;
    }
</style>
```

### 5.2 Level Preview Component (`frontend/src/lib/LevelPreview.svelte`)

```svelte
<script>
    import GameCanvas from './GameCanvas.svelte';

    export let game;
    export let yaml = '';

    let gameCanvas;
    let error = null;
    let applied = false;

    function handleLevelApplied(event) {
        applied = true;
        error = null;
    }

    function handleLevelError(event) {
        error = event.detail.error;
        applied = false;
    }
</script>

<div class="preview-container">
    <GameCanvas
        bind:this={gameCanvas}
        {game}
        levelYaml={yaml}
        on:levelApplied={handleLevelApplied}
        on:levelError={handleLevelError}
    />

    {#if error}
        <div class="error-banner">
            <strong>Error:</strong> {error}
        </div>
    {/if}
</div>

<style>
    .preview-container {
        position: relative;
    }

    .error-banner {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(255, 0, 0, 0.9);
        color: white;
        padding: 8px 16px;
        font-size: 14px;
    }
</style>
```

### 5.3 Author Page (`frontend/src/routes/author/+page.svelte`)

```svelte
<script>
    import { onMount } from 'svelte';
    import LevelEditor from '$lib/LevelEditor.svelte';
    import LevelPreview from '$lib/LevelPreview.svelte';

    let games = [];
    let selectedGame = 'containment';
    let schema = null;
    let yaml = '';
    let editor;

    // Template levels for each game
    const templates = {
        containment: `name: My Level
description: A custom level
difficulty: 1
author: Me

objectives:
  type: survive
  time_limit: 60

ball:
  speed: 150
  radius: 20
  spawn: center

environment:
  edges:
    mode: gaps
    gaps:
      - edge: top
        range: [0.4, 0.6]
`,
        sweetphysics: `name: My Level
description: A custom level
difficulty: 1
author: Me

physics:
  gravity: [0, 980]

elements:
  - type: candy
    position: [640, 150]
  - type: rope
    anchor: [640, 50]
    attachment: candy
    length: 100
  - type: goal
    position: [640, 550]
    radius: 60
`
    };

    onMount(async () => {
        // Fetch games
        const res = await fetch('/api/games');
        games = await res.json();

        // Load schema for selected game
        await loadSchema();

        // Start with template
        yaml = templates[selectedGame] || '';
    });

    async function loadSchema() {
        try {
            const res = await fetch(`/api/levels/schema/${selectedGame}`);
            schema = await res.json();
        } catch (e) {
            schema = null;
        }
    }

    async function handleGameChange() {
        await loadSchema();
        yaml = templates[selectedGame] || '';
    }

    function handleYamlChange(event) {
        yaml = event.detail.value;
    }

    async function validateLevel() {
        try {
            const res = await fetch('/api/levels/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ game: selectedGame, yaml })
            });
            const result = await res.json();

            if (result.valid) {
                editor?.clearErrors();
                alert('Level is valid!');
            } else {
                alert(`Validation error: ${result.error}`);
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
        }
    }

    function downloadLevel() {
        const blob = new Blob([yaml], { type: 'text/yaml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'level.yaml';
        a.click();
        URL.revokeObjectURL(url);
    }

    function loadTemplate() {
        yaml = templates[selectedGame] || '';
        editor?.setValue(yaml);
    }
</script>

<main>
    <header>
        <h1>Level Author</h1>
        <div class="controls">
            <select bind:value={selectedGame} on:change={handleGameChange}>
                {#each games as game}
                    <option value={game.slug}>{game.name}</option>
                {/each}
            </select>
            <button on:click={loadTemplate}>New Level</button>
            <button on:click={validateLevel}>Validate</button>
            <button on:click={downloadLevel}>Download</button>
        </div>
    </header>

    <div class="author-layout">
        <div class="editor-pane">
            <h3>YAML Editor</h3>
            <LevelEditor
                bind:this={editor}
                value={yaml}
                {schema}
                on:change={handleYamlChange}
            />
        </div>

        <div class="preview-pane">
            <h3>Live Preview</h3>
            <LevelPreview
                game={selectedGame}
                {yaml}
            />
        </div>
    </div>
</main>

<style>
    main {
        height: 100vh;
        display: flex;
        flex-direction: column;
        padding: 16px;
        box-sizing: border-box;
    }

    header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        flex-shrink: 0;
    }

    h1 {
        color: #00d9ff;
        margin: 0;
    }

    .controls {
        display: flex;
        gap: 8px;
    }

    .controls select, .controls button {
        padding: 8px 16px;
        border-radius: 4px;
        border: 1px solid rgba(255,255,255,0.2);
        background: #16213e;
        color: #fff;
        cursor: pointer;
    }

    .controls button:hover {
        background: #1e3a5f;
    }

    .author-layout {
        flex: 1;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        min-height: 0;
    }

    .editor-pane, .preview-pane {
        display: flex;
        flex-direction: column;
        background: #16213e;
        border-radius: 8px;
        padding: 16px;
        min-height: 0;
    }

    .editor-pane h3, .preview-pane h3 {
        margin: 0 0 12px;
        color: #888;
        font-size: 14px;
        flex-shrink: 0;
    }

    @media (max-width: 900px) {
        .author-layout {
            grid-template-columns: 1fr;
            grid-template-rows: 1fr 1fr;
        }
    }
</style>
```

### 5.4 Level API Endpoints (`ams/web_controller/level_api.py`)

```python
"""Level management API endpoints."""
from pathlib import Path
from typing import Any, Dict

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from games.registry import GameRegistry

router = APIRouter(prefix="/api/levels", tags=["levels"])
registry = GameRegistry()


class ValidateRequest(BaseModel):
    game: str
    yaml: str


class ValidateResponse(BaseModel):
    valid: bool
    error: str | None = None


@router.post("/validate", response_model=ValidateResponse)
async def validate_level(request: ValidateRequest):
    """Validate level YAML against game schema."""
    try:
        # Parse YAML
        data = yaml.safe_load(request.yaml)
        if not data:
            return ValidateResponse(valid=False, error="Empty YAML")

        # Get game's level loader
        game_class = registry.get_game_class(request.game)
        if not game_class or not game_class.LEVELS_DIR:
            return ValidateResponse(valid=False, error="Game does not support levels")

        # Create loader and validate
        game = game_class.__new__(game_class)
        game.LEVELS_DIR = game_class.LEVELS_DIR
        loader = game._create_level_loader()

        # Try to parse - this validates structure
        loader._parse_level_data(data, Path("temp.yaml"))

        return ValidateResponse(valid=True)

    except yaml.YAMLError as e:
        return ValidateResponse(valid=False, error=f"YAML syntax error: {e}")
    except Exception as e:
        return ValidateResponse(valid=False, error=str(e))


@router.get("/schema/{game}")
async def get_level_schema(game: str) -> Dict[str, Any]:
    """Get JSON Schema for game's level format."""
    # TODO: Generate from dataclasses
    # For now, return basic schema
    schemas = {
        "containment": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
                "author": {"type": "string"},
            },
            "required": ["name"]
        },
        "sweetphysics": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
                "elements": {"type": "array"},
            },
            "required": ["name", "elements"]
        }
    }

    if game not in schemas:
        raise HTTPException(404, f"Schema not found for game: {game}")

    return schemas[game]


@router.get("/{game}")
async def list_game_levels(game: str) -> Dict[str, Any]:
    """List available levels and groups for a game."""
    game_class = registry.get_game_class(game)
    if not game_class or not game_class.LEVELS_DIR:
        raise HTTPException(404, f"Game not found or has no levels: {game}")

    # Create temporary instance to access loader
    game_instance = game_class.__new__(game_class)
    game_instance.LEVELS_DIR = game_class.LEVELS_DIR
    game_instance._level_loader = None
    game_instance._init_level_support(level=None, level_group=None, list_levels=False, choose_level=False)

    loader = game_instance._level_loader
    if not loader:
        return {"levels": [], "groups": []}

    levels = []
    for slug in loader.list_levels():
        info = loader.get_level_info(slug)
        if info:
            levels.append({
                "slug": slug,
                "name": info.name,
                "description": info.description,
                "difficulty": info.difficulty,
                "author": info.author,
            })

    groups = []
    for slug in loader.list_groups():
        info = loader.get_level_info(slug)
        if info:
            groups.append({
                "slug": slug,
                "name": info.name,
                "description": info.description,
                "levels": info.levels,
            })

    return {"levels": levels, "groups": groups}
```

### 5.5 Add API Router to Server

In `ams/web_controller/server.py`:

```python
from ams.web_controller.level_api import router as level_router

# After creating app
app.include_router(level_router)
```

---

## Phase 6: Polish and Testing

### 6.1 Mobile Touch Optimization
- Test touch input on iOS Safari and Android Chrome
- Add touch-action CSS properties
- Handle multi-touch (ignore secondary touches)

### 6.2 Performance Tuning
- Remove all `print()` statements from game code paths
- Profile WASM bundle size, optimize if >50MB
- Consider lazy loading of games
- Add loading indicators

### 6.3 Error Handling
- WebSocket reconnection with exponential backoff
- Graceful degradation if WASM fails to load
- User-friendly error messages

### 6.4 Documentation
- Update CLAUDE.md with browser deployment info
- Create user guide for level authoring
- Document build process

---

## Implementation Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| 1. Browser Runtime | 1-2 weeks | None |
| 2. Build System | 3-5 days | Phase 1 |
| 3. Play Mode UI | 1 week | Phase 1, 2 |
| 4. Observer Mode | 1 week | Can parallel Phase 3 |
| 5. Level Authoring | 1-2 weeks | Phase 3 |
| 6. Polish | 1 week | All phases |

**Total Estimate: 5-7 weeks**

---

## Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Pymunk WASM issues | **Confirmed** | High | Pure Python physics alternative (see below) |
| Large bundle size | Medium | Medium | Code splitting, CDN caching |
| Mobile touch latency | Medium | Medium | Debounce, prediction |
| WebSocket reliability | Low | Medium | Reconnection logic |

---

## Known WASM-Incompatible Libraries

These Python libraries use native C extensions and **do not work in pygbag WASM**:

| Library | Reason | Status | Alternative |
|---------|--------|--------|-------------|
| **Pydantic** | Rust extensions | Fixed | Dataclass-based `browser_models/` |
| **PyYAML** | C libyaml bindings | Fixed | Build-time YAML→JSON conversion |
| **python-dotenv** | N/A in browser | Fixed | Conditional import |
| **pymunk** | CFFI + Chipmunk2D C library | **Blocking** | Pure Python physics (planned) |

### Pymunk Alternative: Pure Python Physics

For SweetPhysics (Cut the Rope style game), a pure Python physics implementation is feasible:

**Required features:**
- Verlet integration for stable simulation
- Distance constraints for rope physics (chain of connected particles)
- Circle-circle collision detection (candy ↔ goal)
- Circle-segment collision (candy ↔ walls)
- Gravity and damping

**Implementation approach:**
```python
# games/common/physics/verlet.py - Pure Python physics
class VerletParticle:
    """Particle with position, previous position, and acceleration."""
    def __init__(self, x, y, mass=1.0, pinned=False):
        self.pos = [x, y]
        self.prev = [x, y]
        self.acc = [0, 0]
        self.mass = mass
        self.pinned = pinned

class DistanceConstraint:
    """Maintains fixed distance between two particles."""
    def __init__(self, p1, p2, rest_length=None, stiffness=1.0):
        ...

class PhysicsWorld:
    """Pure Python physics simulation."""
    def update(self, dt):
        # 1. Apply gravity to acceleration
        # 2. Verlet integration: new_pos = pos + (pos - prev) + acc * dt^2
        # 3. Satisfy constraints (iterate multiple times)
        # 4. Collision detection and response
```

**Priority:** Low - focus on browser infrastructure first, add physics later for SweetPhysics support.

---

## Resources

- [Pygbag Documentation](https://pygame-web.github.io/wiki/pygbag/)
- [Pygbag Code FAQ](https://pygame-web.github.io/wiki/pygbag-code/)
- [Pymunk WASM Demo](https://pmp-p.github.io/pygame-wasm/pygame.html?org.chipmunk6.pymunk04)
- [Monaco Editor](https://microsoft.github.io/monaco-editor/)
- [SvelteKit Documentation](https://kit.svelte.dev/docs)
