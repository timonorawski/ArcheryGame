# AMS Web Controller Architecture

Mobile control interface for AMS games, enabling "bow in hand" operation where the user controls games from their phone while physically using the projectile system.

## Overview

The web controller provides a real-time mobile interface for:
- Selecting detection backend (mouse, laser, object detection)
- Configuring game pacing (archery, throwing, blaster)
- Launching games with custom configuration
- In-game controls (pause, resume, retrieval mode)
- Live game state display (score, hits, time)

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           User's Phone                                   │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Svelte Frontend (SPA)                          │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │  │
│  │  │  Backend    │ │   Pacing    │ │    Game     │ │    Game     │ │  │
│  │  │  Selector   │ │  Selector   │ │  Launcher   │ │   Config    │ │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │  │
│  │  │    Game     │ │    Game     │ │  Connection │                 │  │
│  │  │  Controls   │ │    State    │ │   Status    │                 │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘                 │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket (real-time)
                                    │ + HTTP (static files)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        AMS Host Machine                                  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                   FastAPI Server (uvicorn)                        │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │  │
│  │  │  WebSocket      │  │  REST API       │  │  Static Files   │   │  │
│  │  │  /ws            │  │  /api/state     │  │  /              │   │  │
│  │  │  (state sync)   │  │  /api/health    │  │  (Svelte dist)  │   │  │
│  │  └────────┬────────┘  └─────────────────┘  └─────────────────┘   │  │
│  └───────────┼───────────────────────────────────────────────────────┘  │
│              │                                                           │
│              ▼                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                   AMSWebIntegration                               │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │  │
│  │  │  Command    │ │   State     │ │   Backend   │ │    Game     │ │  │
│  │  │  Handlers   │ │  Broadcast  │ │  Management │ │  Lifecycle  │ │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              │                                                           │
│              ▼                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      AMS Session + Game                           │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │  │
│  │  │  Detection      │  │  Game Registry  │  │  Active Game    │   │  │
│  │  │  Backend        │  │  (auto-discover)│  │  Instance       │   │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              │                                                           │
│              ▼                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Pygame Display (Projector)                     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

### Frontend (Svelte)

Location: `ams/web_controller/frontend/`

Single-page application built with Svelte and Vite. Optimized for mobile touch interaction.

#### Components

| Component | Purpose |
|-----------|---------|
| `App.svelte` | Main app, WebSocket connection, state management |
| `BackendSelector.svelte` | Mouse/Laser/Object backend selection + calibration |
| `PacingSelector.svelte` | Archery/Throwing/Blaster pacing selection |
| `GameLauncher.svelte` | Game list display, launch/stop buttons |
| `GameConfig.svelte` | Modal overlay for game-specific configuration |
| `GameControls.svelte` | Pause/Resume/Retrieval buttons during gameplay |
| `GameState.svelte` | Live score, hits, misses, time display |
| `ConnectionStatus.svelte` | WebSocket connection indicator |
| `SessionInfo.svelte` | Collapsible session details |

#### State Flow

```
Server State ──WebSocket──► sessionInfo, gameState
                                    │
                                    ▼
                           Svelte Reactivity
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              UI Updates      Derived State    Conditionals
              (bindings)    (isGameRunning)   (show/hide)
```

### Backend (Python)

#### WebController (`server.py`)

FastAPI server running in a background thread with its own asyncio event loop.

```python
class WebController:
    """
    - Serves static Svelte frontend
    - WebSocket endpoint for real-time state sync
    - REST endpoints for health checks
    - Command handler registration
    - Background thread with uvicorn
    """
```

**Key Features:**
- Runs on `0.0.0.0:8080` by default (configurable)
- Auto-reconnect on client disconnect
- Broadcast state to all connected clients
- JSON command/response protocol

#### AMSWebIntegration (`ams_integration.py`)

Bridges the web controller to the AMS system.

```python
class AMSWebIntegration:
    """
    - Manages detection backend lifecycle
    - Handles game launching with configuration
    - Routes pygame events to games
    - Broadcasts state updates to web clients
    - Renders idle screen with connection URLs
    """
```

**State Machine:**
```
IDLE ──launch_game──► GAME_RUNNING ──pause──► GAME_PAUSED
  ▲                        │                       │
  │                        │ retrieval             │ resume
  │                        ▼                       │
  │                   RETRIEVAL ◄──────────────────┘
  │                        │
  └────stop_game───────────┴──────game_over────────┘
```

## Communication Protocol

### WebSocket Messages

#### Server → Client (State Updates)

```json
{
  "type": "state",
  "game": {
    "game_name": "Balloon Pop",
    "level_name": "Tutorial 1",
    "state": "playing",
    "score": 1500,
    "time_elapsed": 45.2,
    "hits": 12,
    "misses": 3,
    "extra": {
      "actions": [
        {"id": "retry", "label": "Restart Level", "style": "secondary"}
      ]
    }
  },
  "session": {
    "available_games": ["balloonpop", "containment", ...],
    "game_info": {
      "containment": {
        "name": "Containment",
        "description": "Keep the ball contained",
        "arguments": [...],
        "has_levels": true,
        "levels": [
          {"slug": "tutorial_01", "name": "Tutorial 1", "description": "Learn basics", "difficulty": 1, "author": "AMS"},
          {"slug": "classic", "name": "Classic Mode", "difficulty": 2, "author": "AMS"}
        ],
        "level_groups": [
          {"slug": "campaign", "name": "Campaign", "description": "Story mode", "levels": ["tutorial_01", "level_01", "boss_01"], "level_count": 3}
        ]
      },
      "balloonpop": {
        "name": "Balloon Pop",
        "description": "Pop balloons before they escape",
        "arguments": [
          {"name": "--pacing", "type": "str", "default": "throwing", ...},
          {"name": "--max-escaped", "type": "int", "default": 3, ...}
        ],
        "has_levels": false,
        "levels": [],
        "level_groups": []
      }
    },
    "current_game": "containment",
    "current_level": "tutorial_01",
    "current_level_group": "campaign",
    "detection_backend": "mouse",
    "pacing": "throwing",
    "calibrated": true
  }
}
```

#### Client → Server (Commands)

```json
{"command": "set_backend", "payload": {"backend": "laser"}}
{"command": "set_pacing", "payload": {"pacing": "archery"}}
{"command": "calibrate", "payload": {}}
{"command": "launch_game", "payload": {"game": "balloonpop", "config": {"max_escaped": 5}}}
{"command": "launch_game", "payload": {"game": "containment", "level": "tutorial_01"}}
{"command": "launch_game", "payload": {"game": "containment", "level_group": "campaign"}}
{"command": "pause", "payload": {}}
{"command": "resume", "payload": {}}
{"command": "retrieval", "payload": {}}
{"command": "stop_game", "payload": {}}
{"command": "game_action", "payload": {"action": "retry"}}
```

#### Server → Client (Command Response)

```json
{
  "type": "command_response",
  "command": "launch_game",
  "success": true,
  "result": {"game": "balloonpop", "status": "launched"}
}
```

## Game Actions

Games can expose contextual actions that appear in the web UI during gameplay. Actions change based on game state (e.g., "Retry Level" when lost, "Next Level" when won).

### Action Flow

```
Game State Change → get_available_actions() → Broadcast to Clients → UI Buttons
                                                                          │
User Tap → game_action command → execute_action(id) → State Update → Broadcast
```

### Action Format

Actions returned by `game.get_available_actions()`:

```json
[
  {"id": "retry", "label": "Restart Level", "style": "secondary"},
  {"id": "skip", "label": "Skip Level", "style": "secondary"},
  {"id": "next", "label": "Next Level", "style": "primary"}
]
```

| Field | Description |
|-------|-------------|
| `id` | Unique identifier passed to `execute_action()` |
| `label` | Button text shown to user |
| `style` | Visual hint: `primary` (cyan), `secondary` (gray), `danger` (red) |

### Common Actions

| Action ID | When Available | Description |
|-----------|----------------|-------------|
| `retry` | Level active | Restart current level |
| `skip` | Level lost (in group) | Skip to next level |
| `next` | Level won (in group) | Advance to next level |

Games can define any actions they need. The web UI renders them dynamically.

## Game Configuration System

Games advertise their configurable parameters via `ARGUMENTS` class attribute:

```python
class BalloonPopGame(BaseGame):
    ARGUMENTS = [
        {
            'name': '--pacing',
            'type': str,
            'default': 'throwing',
            'choices': ['archery', 'throwing', 'blaster'],
            'help': 'Device speed preset'
        },
        {
            'name': '--max-escaped',
            'type': int,
            'default': 3,
            'help': 'Balloons that can escape before game over'
        },
    ]
```

The web UI dynamically generates form inputs based on these definitions:
- `choices` → dropdown select
- `type: int/float` → number input
- `type: bool` → checkbox
- `type: str` → text input

## Network Discovery

On startup (before fullscreen), the system enumerates network interfaces:

```python
def get_local_ips() -> List[str]:
    """Get all non-localhost IP addresses"""

def get_mdns_hostname() -> Optional[str]:
    """Get .local hostname if mDNS available"""
```

This triggers the macOS permission prompt while the terminal is visible, avoiding the prompt being hidden behind a fullscreen window.

The idle screen displays:
1. mDNS hostname (e.g., `http://macbook.local:8080`) - most user-friendly
2. IP addresses (e.g., `http://192.168.1.100:8080`) - fallback

## File Structure

```
ams/web_controller/
├── __init__.py              # Exports WebController, GameState, SessionInfo
├── server.py                # FastAPI server, WebSocket handling
├── ams_integration.py       # AMS integration, game lifecycle
├── test_server.py           # Standalone test with simulated state
├── README.md                # Usage documentation
└── frontend/
    ├── package.json         # Svelte/Vite dependencies
    ├── vite.config.js       # Vite configuration with proxy
    ├── index.html           # Entry point
    └── src/
        ├── App.svelte       # Main application
        ├── main.js          # Svelte mount
        └── lib/
            ├── BackendSelector.svelte
            ├── PacingSelector.svelte
            ├── GameLauncher.svelte
            ├── GameConfig.svelte
            ├── GameControls.svelte
            ├── GameState.svelte
            ├── SessionInfo.svelte
            └── ConnectionStatus.svelte
```

## Entry Point

```bash
# Start web-controlled AMS
python ams_web.py

# Fullscreen on projector
python ams_web.py --fullscreen --display 1

# Custom port
python ams_web.py --port 8888
```

## Threading Model

```
Main Thread (pygame)              Background Thread (uvicorn)
─────────────────────             ──────────────────────────
pygame.init()                     asyncio event loop
  │                                 │
  ├─► game loop                     ├─► FastAPI routes
  │     │                           │     │
  │     ├─► handle_pygame_events    │     ├─► WebSocket accept
  │     │     (re-post mouse)       │     │
  │     ├─► integration.update()    │     ├─► receive commands
  │     │     │                     │     │     │
  │     │     ├─► game.update()     │     │     └─► handler callbacks
  │     │     │                     │     │           (thread-safe)
  │     │     └─► broadcast_state ──┼─────┼─► send to clients
  │     │                           │     │
  │     └─► integration.render()    │     └─► broadcast messages
  │           │                     │
  │           └─► pygame.display    │
  │                                 │
  └─► cleanup                       └─► server.should_exit
```

State updates use `asyncio.run_coroutine_threadsafe()` to safely broadcast from the main thread to the asyncio event loop.

## Pacing System

Three pacing tiers based on projectile type:

| Tier | Cycle Time | Use Case |
|------|------------|----------|
| `archery` | 3-8s | Bows, crossbows |
| `throwing` | 1-2s | Darts, balls, axes |
| `blaster` | 0.3-0.5s | Nerf, laser pointer |

Games use `scale_for_pacing()` to adjust timing parameters:
- Spawn intervals
- Combo windows
- Target lifetimes

## Future Considerations

1. **QR Code Connection** - Generate QR code on idle screen for easy phone connection
2. **Multiple Players** - Support multiple connected devices with player assignment
3. **Game Preview** - Show game thumbnail/preview in launcher
4. **Settings Persistence** - Remember backend/pacing preferences
5. **Haptic Feedback** - Vibrate phone on hits/misses
6. **Voice Commands** - "Pause", "Resume" via phone microphone

---

## FUTURE: QR Code Authentication

### Problem

In uncontrolled environments (public venues, events, shared spaces), the current "no auth on local network" model is insufficient:
- Multiple untrusted devices on the same network
- Can't assume network isolation
- Need to prevent unauthorized control of the session
- Password entry is friction (typing on phone while holding equipment)

### Solution: QR Code with Embedded Auth Token

The projected QR code contains a URL with a cryptographically secure session token:

```
http://192.168.1.100:8080/?token=a3f8c2e1b9d4...
```

Scanning the QR code is the authentication — no password needed.

### Security Properties

| Property | Implementation |
|----------|----------------|
| **Session-scoped** | Token generated fresh on AMS startup, invalidated on shutdown |
| **Unguessable** | 256-bit cryptographically random token |
| **Single-use option** | Token can be marked "claimed" after first connection |
| **Revocable** | Operator can regenerate token from keyboard, invalidating old QR |
| **No secrets on network** | Token travels in URL, but attacker must physically see the projection |

### Threat Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Physical Space                                    │
│                                                                          │
│    ┌──────────────┐         ┌──────────────────────────────────────┐   │
│    │   Attacker   │         │          Projection Surface           │   │
│    │   (on WiFi)  │         │  ┌────────────────────────────────┐  │   │
│    │              │    👁️    │  │         QR CODE                │  │   │
│    │  Can't see ──┼─────✗───┼─►│  http://...?token=secret       │  │   │
│    │  projection  │         │  │                                 │  │   │
│    └──────────────┘         │  └────────────────────────────────┘  │   │
│                             └──────────────────────────────────────┘   │
│                                           │                              │
│    ┌──────────────┐                       │ 👁️ Can see                   │
│    │  Legitimate  │◄──────────────────────┘                              │
│    │    User      │                                                      │
│    │  (scans QR)  │                                                      │
│    └──────────────┘                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key insight**: The projection surface is a secure side-channel. Only people physically present can see the QR code.

### Authentication Flow

```
┌─────────┐          ┌─────────┐          ┌─────────┐
│   AMS   │          │  Phone  │          │  User   │
└────┬────┘          └────┬────┘          └────┬────┘
     │                    │                    │
     │  Generate token    │                    │
     │  Display QR code   │                    │
     │◄───────────────────┼────────────────────┤ Sees projection
     │                    │                    │
     │                    │◄───────────────────┤ Scans QR
     │                    │                    │
     │  GET /?token=xxx   │                    │
     │◄───────────────────┤                    │
     │                    │                    │
     │  Validate token    │                    │
     │  Set session cookie│                    │
     │────────────────────►                    │
     │                    │                    │
     │  WS /ws            │                    │
     │◄───────────────────┤ (cookie attached)  │
     │                    │                    │
     │  Authenticated ✓   │                    │
     │────────────────────►                    │
     │                    │                    │
```

### Token Modes

#### 1. Open Mode (Current Default)
No token required. For trusted home/private networks.

```python
WEB_CONTROLLER_AUTH = "none"
```

#### 2. Token Mode (Uncontrolled Environments)
QR contains token, validated on connection.

```python
WEB_CONTROLLER_AUTH = "token"
```

#### 3. Single-Claim Mode (High Security)
Token can only be used once. After first connection, QR regenerates.

```python
WEB_CONTROLLER_AUTH = "single_claim"
```

Useful for: public events where you want one controller at a time.

### Implementation Sketch

```python
# server.py additions

import secrets

class WebController:
    def __init__(self, auth_mode: str = "none"):
        self.auth_mode = auth_mode
        self.session_token = secrets.token_urlsafe(32) if auth_mode != "none" else None
        self.token_claimed = False

    def get_connection_url(self) -> str:
        base = f"http://{self.host}:{self.port}"
        if self.session_token:
            return f"{base}/?token={self.session_token}"
        return base

    def regenerate_token(self) -> str:
        """Invalidate old token, generate new one. Called via keyboard shortcut."""
        self.session_token = secrets.token_urlsafe(32)
        self.token_claimed = False
        return self.session_token

    async def validate_token(self, token: str) -> bool:
        if self.auth_mode == "none":
            return True
        if token != self.session_token:
            return False
        if self.auth_mode == "single_claim":
            if self.token_claimed:
                return False
            self.token_claimed = True
            self.regenerate_token()  # New QR for next person
        return True
```

### QR Code Display

Idle screen shows QR code prominently:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                     AMS Ready                               │
│                                                             │
│              ┌─────────────────────┐                        │
│              │ ▄▄▄▄▄ ▄▄▄▄▄ ▄▄▄▄▄ │                        │
│              │ █   █ █▄▄▄█ █   █ │                        │
│              │ █▄▄▄█ █   █ █▄▄▄█ │                        │
│              │ ▄▄▄▄▄ ▄▄▄▄▄ ▄▄▄▄▄ │                        │
│              │ █   █ █   █ █   █ │                        │
│              │ ▀▀▀▀▀ ▀▀▀▀▀ ▀▀▀▀▀ │                        │
│              └─────────────────────┘                        │
│                                                             │
│              Scan to connect                                │
│              ─────────────────                              │
│              Or visit: 192.168.1.100:8080                   │
│                                                             │
│              Press [R] to regenerate QR code                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Considerations

- **Token in URL**: Visible in browser history. Acceptable because token is session-scoped and physically-derived.
- **HTTPS**: Not required for local network, but could add self-signed cert for paranoid mode.
- **Token rotation**: Could auto-rotate every N minutes for extra security.
- **Audit log**: Could log connection attempts with timestamps for post-hoc review.
- **Multiple tokens**: Could generate per-role tokens (controller vs spectator) shown in different QR codes.
