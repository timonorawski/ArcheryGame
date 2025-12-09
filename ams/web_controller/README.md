# AMS Web Controller

Mobile control interface for AMS games.

## Quick Start

### 1. Install Python dependencies

```bash
# In your virtual environment
pip install -r requirements.txt
```

### 2. Build the frontend (optional - fallback HTML works without this)

```bash
cd ams/web_controller/frontend
npm install
npm run build
```

### 3. Run the web-controlled AMS

```bash
# From project root - windowed mode
python ams_web.py

# Fullscreen on projector (display 1)
python ams_web.py --fullscreen --display 1

# Custom port
python ams_web.py --port 8888
```

Open the displayed URL on your phone to control games.

## Usage

Once running, open the web interface on your phone:

1. **Select Backend** - Choose Mouse (dev), Laser, or Object detection
2. **Calibrate** - Run calibration for laser/object backends
3. **Launch Game** - Tap any available game to start
4. **Control** - Pause, Resume, or enter Retrieval mode during gameplay
5. **Stop** - End the current game and return to idle

## Testing (Simulated)

To test the web interface without running actual games:

```bash
python -m ams.web_controller.test_server
```

Open http://localhost:8080 on your phone or browser.

## Development

### Frontend dev server (with hot reload)

```bash
cd ams/web_controller/frontend
npm run dev
```

This starts Vite on port 5173 and proxies API/WebSocket requests to port 8080.
Run the Python test server in another terminal.

### Adding new commands

**Python (ams_integration.py):**
```python
def _handle_my_command(self, payload: dict) -> dict:
    # Handle the command
    return {'status': 'ok'}

# In _register_commands():
self.web_controller.register_command('my_command', self._handle_my_command)
```

**Svelte (App.svelte):**
```javascript
function handleMyCommand() {
  sendCommand('my_command', { param: 'value' });
}
```

## Architecture

```
┌─────────────────────┐     WebSocket      ┌──────────────────┐
│   Svelte Frontend   │ ◄────────────────► │  FastAPI Server  │
│   (Phone Browser)   │    Real-time       │  (Python)        │
└─────────────────────┘    State Sync      └────────┬─────────┘
                                                    │
                                                    ▼
                                           ┌──────────────────┐
                                           │ AMSWebIntegration│
                                           │  - Backend mgmt  │
                                           │  - Game launch   │
                                           │  - State control │
                                           └────────┬─────────┘
                                                    │
                                                    ▼
                                           ┌──────────────────┐
                                           │   AMS Session    │
                                           │   + Game         │
                                           └──────────────────┘
```

## Files

- `server.py` - FastAPI server, WebSocket handling, state broadcasting
- `ams_integration.py` - Integration with AMS session, backend management, game control
- `test_server.py` - Standalone test with simulated game state
- `frontend/` - Svelte app
  - `src/App.svelte` - Main component with WebSocket logic
  - `src/lib/BackendSelector.svelte` - Backend selection UI
  - `src/lib/GameLauncher.svelte` - Game list and launch UI
  - `src/lib/GameControls.svelte` - Pause/Resume/Retrieval controls
  - `src/lib/GameState.svelte` - Score/hits/time display
  - `src/lib/SessionInfo.svelte` - Session details
  - `src/lib/ConnectionStatus.svelte` - Connection indicator

## Commands

| Command | Payload | Description |
|---------|---------|-------------|
| `set_backend` | `{backend: 'mouse'\|'laser'\|'object'}` | Switch detection backend |
| `calibrate` | `{}` | Run calibration |
| `launch_game` | `{game: 'containment'}` | Launch a game |
| `stop_game` | `{}` | Stop current game |
| `pause` | `{}` | Pause game |
| `resume` | `{}` | Resume from pause/retrieval |
| `retrieval` | `{}` | Enter retrieval mode |
