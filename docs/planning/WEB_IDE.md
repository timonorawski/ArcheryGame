# AMS Web IDE

**Epic: Browser-based game creation environment with live preview**

Enable non-developers to create, edit, and share YAML-defined games directly in the browser. No local setup required.

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 0: Browser Engine** | Not Started | WASMOON Lua + ContentFS shim + pygbag tuneup |
| Phase 1: MVP Editor | Not Started | Monaco editor + pygbag preview + hot reload |
| Phase 2: Visual Editors | Not Started | Sprite sheet + level layout editors |
| Phase 3: Debugger | Not Started | Breakpoints, stepping, inspection |
| Phase 4: Sharing | Not Started | Export, shareable links, gallery |

**Prerequisite:** BROWSER_DEPLOYMENT.md Phase 1-3 (Complete)

> **Note:** The YAML game engine has been significantly refactored since the original browser deployment. Phase 0 must verify/fix pygbag compatibility before IDE work begins.

---

## The Problem

Creating YAML games currently requires:
1. Local Python environment with dependencies
2. Text editor knowledge (YAML syntax)
3. Command-line familiarity
4. Understanding of asset paths and structure

This excludes:
- Kids who want to make their own targets
- Non-technical users at events/workshops
- Quick experimentation without setup
- Sharing creations easily

## The Solution

A browser-based IDE that:
- Edits YAML + Lua with intelligent autocomplete
- Shows live game preview (< 100ms reload)
- Provides visual editors for sprites and levels
- Enables debugging Lua behaviors
- Exports shareable games

---

## Architecture

```
+------------------------------------------------------------------+
|                     AMS WEB IDE (Browser)                         |
+------------------------------------------------------------------+
|  +------------------------+     +----------------------------+   |
|  |     EDITOR PANEL       |     |     PREVIEW PANEL          |   |
|  | +--------------------+ |     | +------------------------+ |   |
|  | | Monaco Editor      | | MSG | | pygbag iframe          | |   |
|  | | - YAML + Lua       | |<--->| | - pygame (WASM)        | |   |
|  | +--------------------+ |     | | - WASMOON Lua          | |   |
|  | +--------------------+ |     | | - ContentFS shim       | |   |
|  | | Visual Editors     | |     | +------------------------+ |   |
|  | | - Sprite Sheet     | |     | +------------------------+ |   |
|  | | - Level Layout     | |     | | Debug Panel            | |   |
|  | +--------------------+ |     | | - Entity inspector     | |   |
|  | +--------------------+ |     | | - Lua console          | |   |
|  | | Lua Debugger UI    | |     | +------------------------+ |   |
|  +------------------------+     +----------------------------+   |
|  +--------------------------------------------------------------+|
|  |          WASMOON Layered FS (ContentFS API-compatible)        ||
|  +--------------------------------------------------------------+|
+------------------------------------------------------------------+
```

### Communication Flow

```
Editor saves game.yaml
       │
       ▼
postMessage('file_update', {path, content})
       │
       ▼
WASMOON FS write (via ContentFS shim)
       │
       ▼
RuntimeBridge sends 'hot_reload' to game
       │
       ▼
GameEngine._hot_reload() - re-parse, update entities
       │
       ▼
Preview shows changes (target: < 100ms)
```

### Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Editor | Monaco Editor | VS Code-quality, native JSON Schema |
| UI Framework | **Svelte** | Already used in `ams/web_controller/frontend/` |
| Build Tool | **Vite** | Already configured for Svelte frontend |
| Preview Runtime | pygbag | Existing infrastructure |
| Lua Runtime | WASMOON | WebAssembly Lua 5.4 |
| Storage | **WASMOON FS** | Layered virtual FS with ContentFS-compatible shim |

> **Reuse:** Extend existing `ams/web_controller/frontend/` rather than creating new project.

---

## Phase 0: Browser Engine (2-3 weeks)

**Goal:** Get the refactored YAML game engine running in browser with full Lua support.

### Background

The game engine has been significantly refactored since the original browser deployment:
- New `ContentFS` layered filesystem (uses PyFilesystem2 - not Emscripten compatible)
- New `LuaEngine` architecture with subroutine loading (uses lupa - C extension)
- New entity system in `ams/games/game_engine/`
- Moved paths: `lua/behavior/`, `lua/collision_action/`, `lua/generator/`

**Key insight:** YAML games require Lua behaviors to function. Can't stub Lua - must implement WASMOON from the start.

### Tasks

1. **Audit `build/web/` vs current engine**
   - Compare `build/web/game_runtime.py` with new `ams/games/game_engine/engine.py`
   - Identify missing modules and changed imports
   - List incompatible dependencies (lupa, PyFilesystem2)

2. **WASMOON Lua Runtime**
   - Integrate WASMOON (Lua 5.4 in WebAssembly) via JavaScript
   - Implement Python↔JS↔Lua bridge using postMessage
   - Port all 60+ `ams.*` API functions to JavaScript
   - Apply same sandbox restrictions as native LuaEngine

3. **ContentFS Shim for WASMOON FS**
   - WASMOON includes a layered virtual filesystem
   - Create `ams/content_fs_browser.py` as shim with same interface
   - Use WASMOON's FS for Lua script loading and assets

4. **Update build script**
   - `games/browser/build.py` → update for new module structure
   - Copy new game files to `build/web/`
   - Bundle WASMOON and Lua scripts

5. **Test deployment**
   - Run `python games/browser/build.py --dev`
   - Verify YAML game loads with working Lua behaviors
   - Test entity spawning, collisions, behaviors

### Files to Create/Modify

```
ams/
└── content_fs_browser.py      # ContentFS shim over WASMOON's FS

ams/web_controller/frontend/src/lib/lua/
├── WasmoonEngine.js           # WASMOON wrapper with sandbox
├── AmsApi.js                  # JavaScript ams.* implementation
└── LuaBridge.js               # postMessage protocol for Python↔JS

build/web/
├── game_runtime.py            # Update for new engine API
├── wasmoon_bridge.py          # Python side of Lua bridge
└── lua_proxy.py               # Route Lua calls through JS

games/browser/
└── build.py                   # Update module paths + WASMOON bundling
```

### Success Criteria

- [ ] `python games/browser/build.py --dev` succeeds
- [ ] Browser opens, game selector shows YAML games
- [ ] Containment game loads with working Lua behaviors
- [ ] `gravity.lua` behavior executes (entities fall)
- [ ] Collision actions trigger (entities respond to hits)
- [ ] No Python import errors in browser console

---

## Phase 1: MVP Editor (4-6 weeks)

**Goal:** Edit game.yaml in Monaco, see changes in pygbag preview.

### Deliverables

1. **Monaco Editor Integration**
   - Load `game.schema.json` for validation
   - Autocomplete entity types, behaviors, tags
   - Error markers with line numbers
   - Syntax highlighting for YAML + Lua

2. **Split-Pane Layout**
   - Resizable editor | preview panels
   - File tree for multi-file projects
   - Tab support for multiple open files

3. **pygbag Preview**
   - Embed existing `build/web/` in iframe
   - Load game from session filesystem
   - Display runtime errors in IDE

4. **Hot Reload**
   - postMessage bridge: IDE ↔ preview
   - File change detection (debounced)
   - Preserve game state across reloads (optional)

5. **Emscripten Virtual FS**
   - MEMFS for session (in-memory, fast)
   - IDBFS for persistence (IndexedDB backend)
   - Already built into pygbag - just need to wire up hot reload

### Files to Create/Modify

Extend existing `ams/web_controller/frontend/` (Svelte + Vite):

```
ams/web_controller/frontend/
├── author.html                    # NEW: IDE entry point
├── vite.config.js                 # MODIFY: Add author.html to build
├── public/
│   └── schemas/                   # NEW: Copy from ams/games/game_engine/schemas/
│       ├── game.schema.json
│       └── level.schema.json
└── src/
    ├── author.js                  # NEW: IDE entry point
    ├── Author.svelte              # NEW: Main IDE layout
    └── lib/
        ├── MonacoEditor.svelte    # NEW: Monaco wrapper
        ├── FileTree.svelte        # NEW: Project files
        ├── PreviewFrame.svelte    # MODIFY: Add hot reload
        └── EditorBridge.js        # NEW: postMessage protocol
```

Python side:
```
build/web/
├── game_runtime.py                # MODIFY: Add hot reload handler
└── platform_compat.py             # MODIFY: Add file update receiver
```

### Success Criteria

- [ ] Edit `game.yaml`, see changes in < 500ms
- [ ] Schema validation shows errors inline
- [ ] Autocomplete suggests entity types
- [ ] Runtime Lua errors display in IDE

---

## Phase 2: Visual Editors (3-4 weeks)

**Goal:** Non-coders can create sprites and levels visually.

### Sprite Sheet Editor

```
+------------------------------------------------------------------+
|  SPRITE SHEET EDITOR                                              |
+------------------------------------------------------------------+
| +------------------------+  +----------------------------------+ |
| | [Sprite Sheet Image]   |  | Sprite Definition                | |
| | [Selection Rectangle]  |  |                                  | |
| |                        |  | Name: duck_flying_right          | |
| | Zoom: [+][-] 100%      |  | X: 0    Y: 126   W: 37   H: 42   | |
| +------------------------+  | Flip X: [ ] Flip Y: [ ]          | |
|                             | Transparent: [159,227,163]       | |
| +------------------------+  |                                  | |
| | Extracted Sprites      |  | Inherits: _ducks_base            | |
| | > duck_flying_right    |  +----------------------------------+ |
| | > duck_flying_left     |                                       |
| +------------------------+  [ Generate YAML ]                    |
+------------------------------------------------------------------+
```

**Features:**
- Upload sprite sheets (PNG, JPG)
- Drag to select regions
- Auto-detect boundaries (optional)
- Generate `assets.sprites` YAML
- Support sprite inheritance

### Level Layout Editor

```
+------------------------------------------------------------------+
|  LEVEL EDITOR                                    Mode: [Visual]   |
+------------------------------------------------------------------+
| +----------------+  +----------------------------------------+   |
| | Entity Palette |  | Level Grid                             |   |
| |                |  |                                        |   |
| | [brick_blue]   |  |  B B B B B B B B B B                   |   |
| | [brick_red]    |  |  R R R R R R R R R R                   |   |
| | [brick_yellow] |  |  Y Y Y Y Y Y Y Y Y Y                   |   |
| | [invader]      |  |  . . . . . . . . . .                   |   |
| | [...]          |  |                                        |   |
| +----------------+  +----------------------------------------+   |
|                                                                   |
| Grid: 10x5   Brick: 70x25   Start: (65, 60)   Spacing: 0x0       |
+------------------------------------------------------------------+
```

**Features:**
- Visual grid with entity icons
- Click to place, drag to fill
- ASCII mode for power users
- Configure grid parameters
- Preview entity types from palette

### Project Persistence

- Save to Emscripten IDBFS (survives refresh, syncs to IndexedDB)
- Export as ZIP (game.yaml + levels + assets)
- Import from ZIP

### Files to Create

```
ams/web_controller/frontend/src/lib/
├── visual/
│   ├── SpriteSheetEditor.svelte
│   ├── SpriteRegionSelector.svelte
│   ├── LevelEditor.svelte
│   ├── LevelGrid.svelte
│   ├── EntityPalette.svelte
│   └── AsciiEditor.svelte
├── project/
│   ├── ProjectManager.js         # Save/load with IDBFS
│   └── ExportManager.js          # ZIP export
```

### Success Criteria

- [ ] Upload sprite sheet, extract 10+ sprites
- [ ] Create level layout visually
- [ ] Save project, close browser, reopen → project restored
- [ ] Export ZIP, import elsewhere → works

---

## Phase 3: Lua Debugger (2-3 weeks)

**Goal:** Debug behaviors interactively.

### Debugger UI

```
+------------------------------------------------------------------+
|  LUA DEBUGGER                                                     |
+------------------------------------------------------------------+
| [▶ Play] [⏸ Pause] [→ Step] [↓ Step Into]    Frame: 1234         |
+------------------------------------------------------------------+
| +----------------------+  +------------------------------------+ |
| | BREAKPOINTS          |  | WATCH EXPRESSIONS                  | |
| | ● rope_link.lua:34   |  | entity.x         → 400.5           | |
| | ○ gravity.lua:12     |  | entity.vy        → 125.3           | |
| +----------------------+  +------------------------------------+ |
| +----------------------+  +------------------------------------+ |
| | CALL STACK           |  | LOCAL VARIABLES                    | |
| | → rope_link:on_update|  | entity_id: "candy_abc123"          | |
| |   gravity:on_update  |  | dt: 0.016                          | |
| +----------------------+  | rest_length: 30                    | |
+------------------------------------------------------------------+
| CONSOLE                                                           |
| > ams.get_x("candy_abc123")                                       |
| 400.5                                                             |
| > ams.set_prop("candy_abc123", "debug", true)                     |
| nil                                                               |
+------------------------------------------------------------------+
```

### Features

1. **Breakpoint Management**
   - Set breakpoints by clicking line numbers
   - Conditional breakpoints (optional)
   - Persist across sessions

2. **Execution Control**
   - Play/Pause game loop
   - Step Over (next line)
   - Step Into (enter function)
   - Continue to next breakpoint

3. **State Inspection**
   - View local variables at breakpoint
   - Watch expressions (custom)
   - Entity property viewer

4. **Lua Console (REPL)**
   - Execute arbitrary Lua
   - Auto-complete for `ams.*`
   - History (up/down arrows)

### Implementation

WASMOON supports debug hooks:

```typescript
lua.global.set('__ams_debug_hook', (event, line) => {
    if (event === 'line' && breakpoints.has(currentFile, line)) {
        pauseExecution();
        sendToIDE({ type: 'breakpoint_hit', file: currentFile, line });
    }
});

await lua.doString(`
    debug.sethook(__ams_debug_hook, "l")
`);
```

### Files to Create

```
ams/web_controller/frontend/src/lib/debug/
├── Debugger.svelte
├── BreakpointGutter.svelte
├── CallStack.svelte
├── VariableInspector.svelte
├── WatchExpressions.svelte
├── Console.svelte
├── DebugSession.js
├── BreakpointManager.js
└── LuaEvaluator.js
```

### Success Criteria

- [ ] Set breakpoint, execution pauses at line
- [ ] Inspect entity properties at breakpoint
- [ ] Step through `on_update` function
- [ ] Console evaluates `ams.get_x(id)`

---

## Phase 4: Sharing and Polish (2-3 weeks)

**Goal:** Share games with the world.

### Export Options

1. **ZIP Archive**
   - game.yaml + levels/ + lua/ + assets/
   - Importable by other IDE users
   - Works with local Python setup

2. **Standalone HTML**
   - Single file, playable anywhere
   - Embeds all assets as data URIs
   - Includes minimal pygbag runtime

3. **Shareable Link**
   - Small games: URL-encoded data
   - Large games: Server-stored with ID
   - Example: `https://ams.games/play?id=abc123`

### Gallery/Showcase

```
+------------------------------------------------------------------+
|  AMS GAME GALLERY                                                 |
+------------------------------------------------------------------+
| +----------------+ +----------------+ +----------------+          |
| | [Screenshot]   | | [Screenshot]   | | [Screenshot]   |          |
| | Space Bricks   | | Duck Hunt Rem  | | Fruit Ninja    |          |
| | by @creator    | | by @hunter     | | by @slicer     |          |
| | ★★★★☆ (42)     | | ★★★★★ (128)    | | ★★★★☆ (67)     |          |
| | [Play] [Fork]  | | [Play] [Fork]  | | [Play] [Fork]  |          |
| +----------------+ +----------------+ +----------------+          |
|                                                                   |
| [Upload Your Game]                    Sort: [Popular] [Recent]    |
+------------------------------------------------------------------+
```

### Hosting Options

**Option A: Static (Vercel/Netlify/GitHub Pages)**
- IDE + pygbag bundle
- Games in localStorage only
- Sharing via URL-encoded data (size limited)

**Option B: With Backend (Recommended for sharing)**
- Simple API: POST game → ID, GET game by ID
- CDN for WASM bundles
- Optional user accounts
- Gallery with ratings

### Files to Create

```
ams/web_controller/frontend/src/lib/
├── sharing/
│   ├── ExportZip.js
│   ├── ExportHtml.js
│   └── ShareLink.js
├── Gallery.svelte
├── ExportDialog.svelte
└── ShareDialog.svelte
```

### Success Criteria

- [ ] Export ZIP, import on another machine
- [ ] Generate shareable link
- [ ] Open link → game plays immediately
- [ ] Browse gallery, fork game to edit

---

## Security Considerations

### Lua Sandbox (WASMOON)

Apply identical restrictions as Python `LuaEngine`:

```lua
-- BLOCKED
io = nil
os = nil
debug = nil
package = nil
require = nil
loadfile = nil
dofile = nil
load = nil
rawget = nil
rawset = nil
getmetatable = nil
setmetatable = nil

-- ALLOWED
math.*
string.* (except string.dump, string.rep limited)
pairs, ipairs, type, tonumber, tostring
pcall, error, next
```

### User Content

- Sanitize uploaded files (images only)
- No server-side code execution
- CSP headers prevent XSS
- Same-origin iframe policy

### Storage Limits

- Warn at 50MB project size
- IndexedDB quota varies by browser
- Offer export for large projects

---

## Phase 0 Technical Deep Dive: Python↔JS↔Lua Bridge

This section provides detailed implementation guidance for the WASMOON integration.

### The Challenge

The native LuaEngine uses `lupa`, a Python-Lua bridge via C extension. C extensions don't work in WebAssembly. We need a three-way bridge:

```
┌──────────────────┐     postMessage      ┌──────────────────┐
│   Python/pygbag  │ <─────────────────> │   JavaScript     │
│   (Emscripten)   │                      │   (main thread)  │
│                  │                      │                  │
│  GameEngine      │                      │  WASMOON Engine  │
│  LuaProxy        │                      │  AmsApi.js       │
│  ContentFS shim  │                      │  LuaBridge.js    │
└──────────────────┘                      └──────────────────┘
                                                   │
                                          Lua 5.4 VM (WASM)
                                                   │
                                          ┌──────────────────┐
                                          │  Lua behaviors   │
                                          │  gravity.lua     │
                                          │  bounce.lua      │
                                          └──────────────────┘
```

### Message Protocol

```typescript
// Python → JavaScript (Lua execution request)
interface LuaExecRequest {
    type: 'lua_exec';
    id: number;               // For response correlation
    action: 'load_subroutine' | 'call_method' | 'eval_expression';
    subroutine_type?: string; // 'behavior', 'collision_action', etc.
    subroutine_name?: string;
    lua_code?: string;        // For inline Lua or load
    method?: string;          // 'on_update', 'on_spawn', 'execute'
    args?: any[];             // [entity_id, dt] or [a_id, b_id, modifier]
}

// JavaScript → Python (API calls from Lua)
interface AmsApiCall {
    type: 'ams_api';
    id: number;
    fn: string;               // 'get_x', 'set_vy', 'spawn', etc.
    args: any[];
}

// Python → JavaScript (API response)
interface AmsApiResponse {
    type: 'ams_api_response';
    id: number;
    result: any;
}

// JavaScript → Python (Lua execution result)
interface LuaExecResponse {
    type: 'lua_exec_response';
    id: number;
    success: boolean;
    result?: any;
    error?: string;
}
```

### WASMOON Integration (JavaScript Side)

```javascript
// ams/web_controller/frontend/src/lib/lua/WasmoonEngine.js

import { LuaFactory } from 'wasmoon';

export class WasmoonEngine {
    constructor() {
        this.lua = null;
        this.subroutines = new Map();  // type -> name -> lua table
        this.apiCallId = 0;
        this.pendingApiCalls = new Map();
    }

    async init() {
        const factory = new LuaFactory();
        this.lua = await factory.createEngine();
        this._applySandbox();
        this._registerAmsNamespace();
    }

    _applySandbox() {
        // Apply same restrictions as Python LuaEngine
        this.lua.doString(`
            -- Clear dangerous globals
            io = nil
            os = nil
            debug = nil
            package = nil
            require = nil
            loadfile = nil
            dofile = nil
            load = nil
            rawget = nil
            rawset = nil
            getmetatable = nil
            setmetatable = nil
            collectgarbage = nil
            _G = nil
            coroutine = nil

            -- Clear string.dump (security risk)
            string.dump = nil
            string.rep = nil
        `);
    }

    _registerAmsNamespace() {
        // Create ams namespace with all API functions
        const ams = {};

        // Transform
        ams.get_x = (id) => this._callPythonApi('get_x', [id]);
        ams.set_x = (id, x) => this._callPythonApi('set_x', [id, x]);
        ams.get_y = (id) => this._callPythonApi('get_y', [id]);
        ams.set_y = (id, y) => this._callPythonApi('set_y', [id, y]);
        ams.get_vx = (id) => this._callPythonApi('get_vx', [id]);
        ams.set_vx = (id, vx) => this._callPythonApi('set_vx', [id, vx]);
        ams.get_vy = (id) => this._callPythonApi('get_vy', [id]);
        ams.set_vy = (id, vy) => this._callPythonApi('set_vy', [id, vy]);
        ams.get_width = (id) => this._callPythonApi('get_width', [id]);
        ams.get_height = (id) => this._callPythonApi('get_height', [id]);

        // Visual
        ams.get_sprite = (id) => this._callPythonApi('get_sprite', [id]);
        ams.set_sprite = (id, s) => this._callPythonApi('set_sprite', [id, s]);
        ams.get_color = (id) => this._callPythonApi('get_color', [id]);
        ams.set_color = (id, c) => this._callPythonApi('set_color', [id, c]);

        // State
        ams.get_health = (id) => this._callPythonApi('get_health', [id]);
        ams.set_health = (id, h) => this._callPythonApi('set_health', [id, h]);
        ams.is_alive = (id) => this._callPythonApi('is_alive', [id]);
        ams.destroy = (id) => this._callPythonApi('destroy', [id]);

        // Spawning & queries
        ams.spawn = (...args) => this._callPythonApi('spawn', args);
        ams.get_entities_of_type = (t) => this._callPythonApi('get_entities_of_type', [t]);
        ams.get_entities_by_tag = (t) => this._callPythonApi('get_entities_by_tag', [t]);
        ams.count_entities_by_tag = (t) => this._callPythonApi('count_entities_by_tag', [t]);
        ams.get_all_entity_ids = () => this._callPythonApi('get_all_entity_ids', []);

        // Game state
        ams.get_screen_width = () => this._callPythonApi('get_screen_width', []);
        ams.get_screen_height = () => this._callPythonApi('get_screen_height', []);
        ams.get_score = () => this._callPythonApi('get_score', []);
        ams.add_score = (p) => this._callPythonApi('add_score', [p]);
        ams.get_time = () => this._callPythonApi('get_time', []);

        // Events
        ams.play_sound = (s) => this._callPythonApi('play_sound', [s]);
        ams.schedule = (d, c, id) => this._callPythonApi('schedule', [d, c, id]);

        // Properties
        ams.get_prop = (id, k) => this._callPythonApi('get_prop', [id, k]);
        ams.set_prop = (id, k, v) => this._callPythonApi('set_prop', [id, k, v]);
        ams.get_config = (id, b, k, d) => this._callPythonApi('get_config', [id, b, k, d]);

        // Parent-child
        ams.get_parent_id = (id) => this._callPythonApi('get_parent_id', [id]);
        ams.set_parent = (...args) => this._callPythonApi('set_parent', args);
        ams.detach_from_parent = (id) => this._callPythonApi('detach_from_parent', [id]);
        ams.get_children = (id) => this._callPythonApi('get_children', [id]);
        ams.has_parent = (id) => this._callPythonApi('has_parent', [id]);

        // Math helpers (can be computed locally)
        ams.sin = Math.sin;
        ams.cos = Math.cos;
        ams.sqrt = Math.sqrt;
        ams.atan2 = Math.atan2;
        ams.random = Math.random;
        ams.random_range = (min, max) => min + Math.random() * (max - min);
        ams.clamp = (v, min, max) => Math.max(min, Math.min(max, v));
        ams.log = (msg) => console.log('[Lua]', msg);

        this.lua.global.set('ams', ams);
    }

    _callPythonApi(fn, args) {
        // Synchronous call to Python via postMessage + SharedArrayBuffer
        // OR batch calls and process at frame boundaries
        // Implementation depends on whether we need sync or can batch
        return this._syncCallPython(fn, args);
    }

    loadSubroutine(type, name, luaCode) {
        const result = this.lua.doString(luaCode);
        if (!this.subroutines.has(type)) {
            this.subroutines.set(type, new Map());
        }
        this.subroutines.get(type).set(name, result);
        return true;
    }

    callMethod(type, name, method, ...args) {
        const sub = this.subroutines.get(type)?.get(name);
        if (!sub || !sub[method]) return null;
        return sub[method](...args);
    }
}
```

### Python LuaProxy (Python Side)

```python
# build/web/lua_proxy.py

"""
Lua Proxy - Routes Lua operations through JavaScript WASMOON.

In browser, Lua execution happens in JavaScript via WASMOON.
This proxy maintains the same interface as LuaEngine but delegates
all Lua operations to JavaScript via postMessage.
"""

import json
import sys
from typing import Any, Optional

if sys.platform == "emscripten":
    import platform


class LuaProxy:
    """Browser-compatible proxy for Lua operations via WASMOON."""

    def __init__(self, game_engine):
        self.game_engine = game_engine
        self._call_id = 0
        self._pending = {}

    def load_subroutine(self, sub_type: str, name: str, lua_code: str) -> bool:
        """Send Lua code to WASMOON for loading."""
        return self._send_and_wait('load_subroutine', {
            'subroutine_type': sub_type,
            'subroutine_name': name,
            'lua_code': lua_code
        })

    def call_behavior_method(self, behavior_name: str, method: str,
                             entity_id: str, *args) -> Any:
        """Call a behavior method in WASMOON."""
        return self._send_and_wait('call_method', {
            'subroutine_type': 'behavior',
            'subroutine_name': behavior_name,
            'method': method,
            'args': [entity_id, *args]
        })

    def execute_collision_action(self, action_name: str,
                                  entity_a_id: str, entity_b_id: str,
                                  modifier: Optional[dict] = None) -> bool:
        """Execute a collision action in WASMOON."""
        return self._send_and_wait('call_method', {
            'subroutine_type': 'collision_action',
            'subroutine_name': action_name,
            'method': 'execute',
            'args': [entity_a_id, entity_b_id, modifier]
        })

    def evaluate_expression(self, expression: str) -> Any:
        """Evaluate a Lua expression in WASMOON."""
        return self._send_and_wait('eval_expression', {
            'lua_code': expression
        })

    def _send_and_wait(self, action: str, data: dict) -> Any:
        """Send message to JS and wait for response."""
        self._call_id += 1
        msg = {
            'type': 'lua_exec',
            'id': self._call_id,
            'action': action,
            **data
        }

        # Send to JavaScript
        platform.window.postMessage(json.dumps(msg), '*')

        # In async context, would await response
        # For sync, need SharedArrayBuffer or frame-boundary batching
        # This is a simplified placeholder
        return None

    def handle_api_call(self, fn: str, args: list) -> Any:
        """Handle ams.* API call from JavaScript WASMOON."""
        api_map = {
            'get_x': lambda id: self._get_entity_attr(id, 'x'),
            'set_x': lambda id, x: self._set_entity_attr(id, 'x', x),
            'get_y': lambda id: self._get_entity_attr(id, 'y'),
            'set_y': lambda id, y: self._set_entity_attr(id, 'y', y),
            # ... (all 40+ API functions)
        }

        if fn in api_map:
            return api_map[fn](*args)
        return None

    def _get_entity_attr(self, entity_id: str, attr: str) -> Any:
        entity = self.game_engine.get_entity(entity_id)
        return getattr(entity, attr, None) if entity else None

    def _set_entity_attr(self, entity_id: str, attr: str, value: Any):
        entity = self.game_engine.get_entity(entity_id)
        if entity:
            setattr(entity, attr, value)
```

### Synchronization Strategy

The key challenge is that Lua behaviors make synchronous `ams.*` calls, but postMessage is async. Options:

**Option A: SharedArrayBuffer (Fast, Complex)**
- Use Atomics.wait() to block JS while Python responds
- Requires cross-origin isolation headers
- Best performance for real-time games

**Option B: Frame Boundary Batching (Simpler, Good Enough)**
- Lua records all `ams.*` calls into a list
- At end of `on_update`, send batch to Python
- Python applies all changes, sends updated state
- Next frame uses cached state
- Slight state lag (1 frame) but much simpler

**Option C: State Snapshot (Simplest)**
- Before calling Lua, serialize relevant entity state to JS
- Lua operates on local JS copy
- After Lua completes, serialize changes back to Python
- Best for behaviors that don't need global queries

### Recommended Approach: Hybrid

1. **Math helpers** (`sin`, `cos`, `random`, etc.) - Pure JS, no roundtrip
2. **Entity property access** (`get_x`, `set_x`) - State snapshot per entity
3. **Global queries** (`get_entities_by_tag`) - Pre-computed before Lua call
4. **Spawning** (`spawn`) - Deferred, applied after Lua completes

```javascript
// Before calling on_update for entity:
const snapshot = {
    x: entity.x, y: entity.y,
    vx: entity.vx, vy: entity.vy,
    // ... other props
};

// During Lua execution, ams.get_x returns snapshot.x
// ams.set_x updates snapshot, not Python directly

// After on_update completes:
postMessage({ type: 'apply_state', entity_id: id, changes: snapshot });
```

### ContentFS Browser Shim

```python
# ams/content_fs_browser.py

"""
Browser-compatible ContentFS using Emscripten's virtual filesystem.

In browser, files are loaded into Emscripten's MEMFS during build.
This shim provides the same interface as ContentFS but reads from
the Emscripten virtual filesystem.
"""

import sys
from typing import Optional, Iterator


class ContentFSBrowser:
    """Browser-compatible ContentFS shim over Emscripten FS."""

    def __init__(self, base_path: str = '/game'):
        self._base = base_path
        self._core_dir = base_path  # For compatibility

    @property
    def core_dir(self):
        """Compatibility with native ContentFS."""
        return self._core_dir

    def exists(self, path: str) -> bool:
        """Check if path exists in Emscripten FS."""
        import os
        full_path = f"{self._base}/{path}"
        return os.path.exists(full_path)

    def readtext(self, path: str, encoding: str = 'utf-8') -> str:
        """Read text file from Emscripten FS."""
        full_path = f"{self._base}/{path}"
        with open(full_path, 'r', encoding=encoding) as f:
            return f.read()

    def listdir(self, path: str) -> list[str]:
        """List directory contents from Emscripten FS."""
        import os
        full_path = f"{self._base}/{path}"
        return os.listdir(full_path)

    def add_game_layer(self, game_path) -> bool:
        """No-op in browser - game content already bundled."""
        return True

    def getsyspath(self, path: str) -> str:
        """Return Emscripten virtual path."""
        return f"{self._base}/{path}"


# Factory function to get appropriate ContentFS
def get_content_fs(core_dir=None):
    """Get ContentFS implementation for current platform."""
    if sys.platform == "emscripten":
        return ContentFSBrowser()
    else:
        from ams.content_fs import ContentFS
        from pathlib import Path
        return ContentFS(core_dir or Path.cwd())
```

### API Function Inventory

Full list of `ams.*` functions that need JavaScript implementations:

| Category | Functions |
|----------|-----------|
| **Transform** | `get_x`, `set_x`, `get_y`, `set_y`, `get_vx`, `set_vx`, `get_vy`, `set_vy`, `get_width`, `get_height` |
| **Visual** | `get_sprite`, `set_sprite`, `get_color`, `set_color` |
| **State** | `get_health`, `set_health`, `is_alive`, `destroy` |
| **Spawning** | `spawn` |
| **Queries** | `get_entities_of_type`, `get_entities_by_tag`, `count_entities_by_tag`, `get_all_entity_ids` |
| **Game State** | `get_screen_width`, `get_screen_height`, `get_score`, `add_score`, `get_time` |
| **Events** | `play_sound`, `schedule` |
| **Properties** | `get_prop`, `set_prop`, `get_config` |
| **Parent-Child** | `get_parent_id`, `set_parent`, `detach_from_parent`, `get_children`, `has_parent` |
| **Math** | `sin`, `cos`, `sqrt`, `atan2`, `random`, `random_range`, `clamp` |
| **Debug** | `log` |

**Total: 40+ functions** (math helpers can be pure JS, others need Python roundtrip or state snapshot)

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| WASMOON performance | High | Profile early; optimize hot paths; cache compiled Lua |
| lupa API differences | High | Comprehensive test suite; behavior parity tests |
| IndexedDB quota | Medium | Warn user; support external storage; compress assets |
| pygbag version drift | Medium | Pin version; integration tests |
| Large sprite sheets | Medium | Chunked loading; OPFS for big files |
| Mobile browser quirks | Low | Test matrix; graceful degradation |

---

## Open Questions

1. **Hosting model:** Static-only or with backend for sharing?
2. **Collaboration:** Real-time multi-user editing (future scope)?
3. **Mobile:** Touch-friendly editing on tablets (future scope)?
4. **Offline:** Service worker for offline editing?

---

## Resources

- [Monaco Editor](https://microsoft.github.io/monaco-editor/)
- [WASMOON](https://github.com/ceifa/wasmoon)
- [Pygbag](https://pygame-web.github.io/)
- [Vite](https://vitejs.dev/)
- [Svelte](https://svelte.dev/)

---

## Related Documents

- `docs/planning/BROWSER_DEPLOYMENT.md` - Foundation (Phases 1-3 complete)
- `docs/planning/WEB_CONTROLLER.md` - Mobile control interface
- `docs/guides/lua_scripting.md` - Lua API reference
- `docs/guides/GAME_ENGINE_ARCHITECTURE.md` - Engine internals
