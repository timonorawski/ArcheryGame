# Browser Lua Bridge Architecture

This document describes how YAML games execute in the browser via pygbag and a JavaScript Lua runtime.

## Overview

Native YAMS uses Python's Lupa (LuaJIT bindings) for Lua execution. The browser deployment requires:
- **pygbag**: Compiles Python to WebAssembly (pyodide-based)
- **JavaScript Lua runtime**: Executes Lua behaviors in the browser

The browser bridge replicates the native architecture while adapting to the async, sandboxed browser environment.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        BROWSER EXECUTION ENVIRONMENT                          │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Python (pyodide WASM)                                │ │
│  │                                                                         │ │
│  │  ┌─────────────────────┐     ┌─────────────────────────────────────┐  │ │
│  │  │   GameEngine        │────►│   LuaEngineBrowser                  │  │ │
│  │  │   (same as native)  │     │   (games/browser/lua_bridge.py)     │  │ │
│  │  └─────────────────────┘     │                                     │  │ │
│  │                              │  - Serializes entity state to JSON  │  │ │
│  │                              │  - Sends messages via postMessage   │  │ │
│  │                              │  - Applies changes from JS results  │  │ │
│  │                              └──────────────────┬──────────────────┘  │ │
│  └─────────────────────────────────────────────────│──────────────────────┘ │
│                                                    │                        │
│                                      postMessage   │                        │
│                                                    ▼                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    JavaScript (fengari_bridge.js)                       │ │
│  │                                                                         │ │
│  │  ┌─────────────────────┐     ┌─────────────────────────────────────┐  │ │
│  │  │   Entity Storage    │◄────│   Fengari Lua Runtime               │  │ │
│  │  │   (JS mirror)       │     │   (Lua 5.3 in pure JavaScript)      │  │ │
│  │  └─────────────────────┘     │                                     │  │ │
│  │                              │  - Loads subroutines                │  │ │
│  │  ┌─────────────────────┐     │  - Executes behavior.on_update()    │  │ │
│  │  │   ams.* API         │◄────│  - Tracks state changes             │  │ │
│  │  │   (JS functions)    │     └─────────────────────────────────────┘  │ │
│  │  └─────────────────────┘                                              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Message Protocol

Communication between Python (WASM) and JavaScript uses `postMessage`:

### Python → JavaScript Messages

```javascript
// lua_init: Initialize Lua runtime
{ source: 'lua_engine', type: 'lua_init', data: { screen_width, screen_height } }

// lua_load_subroutine: Load Lua code
{ source: 'lua_engine', type: 'lua_load_subroutine', data: { sub_type, name, code } }

// lua_update: Execute frame behaviors
{ source: 'lua_engine', type: 'lua_update', data: { dt, elapsed_time, score, entities: {...} } }

// lua_collision: Execute collision action
{ source: 'lua_engine', type: 'lua_collision', data: { action, entity_a, entity_b, modifier } }
```

### JavaScript → Python Messages

Responses are queued in `window.luaResponses` for Python to poll:

```javascript
// lua_update_result: State changes from behavior execution
{ type: 'lua_update_result', data: { entities: {...}, spawns: [], sounds: [], scheduled: [], score } }

// lua_crashed: Fatal Lua error (game should stop)
{ type: 'lua_crashed', data: { error, context, message } }
```

## Frame Update Flow

```
GameEngine.update(dt)
     │
     ├─ 1. LuaEngineBrowser._execute_behavior_updates(dt)
     │         │
     │         ├─ Serialize all entity states to JSON
     │         │
     │         └─ Send 'lua_update' message with entities dict
     │
     ├─ 2. JavaScript fengari_bridge receives message
     │         │
     │         ├─ Update local entity storage
     │         ├─ Reset state changes tracker
     │         │
     │         └─ For each entity with behaviors:
     │               │
     │               └─ doString(`behavior.on_update(entityId, dt)`)
     │                     │
     │                     ├─ Lua calls ams.set_x(), ams.destroy(), etc.
     │                     │
     │                     └─ Changes recorded in stateChanges
     │
     ├─ 3. JavaScript queues 'lua_update_result'
     │
     └─ 4. BrowserGameRuntime polls and applies results
               │
               └─ LuaEngineBrowser.apply_lua_results(results)
                     │
                     ├─ Apply entity changes
                     ├─ Queue spawns for GameEngine
                     ├─ Queue sounds for Skin
                     └─ Schedule callbacks
```

## Subroutine Loading

Subroutines (behaviors, collision_actions, etc.) are loaded entirely in Lua to preserve function references:

```javascript
// loadSubroutine wraps code to assign directly to Lua global
const wrappedCode = `__subroutine_behavior_${name} = (function() ${code} end)()`;

// Execute in Lua - result never converted to JS
lua_pcall(L, wrappedCode);

// Later, behavior is called via doString:
doString(`__subroutine_behavior_gravity.on_update("entity_123", 0.016)`);
```

**Why not convert to JavaScript?** Lua tables containing functions lose their functions when converted to JS objects. Keeping subroutines in Lua preserves the complete behavior table including all hooks.

## Entity Storage

JavaScript maintains a mirror of entity state for Lua API calls:

```javascript
let entities = {
    'entity_123': {
        id: 'entity_123',
        entity_type: 'ball',
        alive: true,
        x: 100, y: 200,
        vx: 50, vy: -100,
        width: 16, height: 16,
        behaviors: ['gravity', 'destroy_offscreen'],
        behavior_config: { gravity: { acceleration: 800 } },
        properties: { bounces: 0 },
        // ... other fields
    }
};
```

**State changes** are tracked separately and returned to Python:

```javascript
let stateChanges = {
    entities: {
        'entity_123': { x: 150, vy: -50 }  // Only changed fields
    },
    spawns: [{ entity_type: 'particle', x: 100, y: 200 }],
    sounds: ['bounce'],
    scheduled: [{ delay: 1.0, callback: 'on_timer', entity_id: 'entity_123' }],
    score: 10
};
```

## AMS API Implementation

The `ams.*` namespace is implemented as JavaScript functions exposed to Lua:

```javascript
const api = {
    // Transform
    get_x: (id) => entities[id]?.x ?? 0,
    set_x: (id, x) => {
        stateChanges.entities[id] = stateChanges.entities[id] || {};
        stateChanges.entities[id].x = x;
        entities[id].x = x;  // Update local for subsequent reads
    },

    // Spawning
    spawn: (type, x, y, ...) => {
        const spawnId = 'spawn_' + (++spawnCounter);
        stateChanges.spawns.push({ id: spawnId, entity_type: type, x, y, ... });
        return spawnId;
    },

    // Queries
    get_entities_by_tag: (tag) => {
        return Object.values(entities)
            .filter(e => e.alive && e.tags?.includes(tag))
            .map(e => e.id);
    },

    // Math (delegate to JavaScript)
    sin: Math.sin,
    random_range: (min, max) => min + Math.random() * (max - min),
    // ...
};

// Register each function in Lua's ams namespace
for (const [name, fn] of Object.entries(api)) {
    setGlobal('_ams_temp_fn', fn);
    doString(`ams.${name} = _ams_temp_fn`);
}
```

## Error Handling

Lua errors crash the engine to prevent silent corruption:

```javascript
let luaCrashed = false;

function notifyLuaCrash(error, context) {
    luaCrashed = true;

    // Log for debugging
    console.error(`[FENGARI] FATAL: ${context}:`, error);
    streamLog('FATAL', 'lua_crash', JSON.stringify({ error, context }));

    // Notify Python
    window.luaResponses.push(JSON.stringify({
        type: 'lua_crashed',
        data: { error, context, message: `Lua stopped: ${error}` }
    }));
}

function doString(code, context) {
    if (luaCrashed) return null;  // Refuse to execute after crash

    const status = lua_pcall(L, code);
    if (status !== LUA_OK) {
        notifyLuaCrash(lua_tojsstring(L, -1), context);
        return null;
    }
    // ...
}
```

**Design decision**: Lua scripts are core game logic. A Lua error indicates a bug that would cause incorrect behavior. Crashing immediately makes bugs visible rather than silently corrupting game state.

## Lua Runtime Choice: Fengari

### Why Fengari (Current)

**Fengari** is a pure JavaScript implementation of Lua 5.3:

| Pros | Cons |
|------|------|
| No memory constraints | Slower than native/WASM |
| Synchronous execution | Lua 5.3 (not 5.4) |
| Simple integration | Larger bundle size |
| Stable, predictable |  |

### Why Not WASMOON (Initial Attempt)

**WASMOON** is Lua 5.4 compiled to WebAssembly. We initially chose it for:
- Performance (near-native Lua speed)
- Lua 5.4 compatibility with native Lupa

**It failed due to memory corruption:**
- "memory access out of bounds" crashes after ~1-2 seconds
- Processing 52 entities/frame with JSON serialization exceeded WASM heap limits
- Both `doString()` with embedded JSON and `global.set()` approaches failed
- The WASM heap fragmented and corrupted after ~100 frames

**Root cause**: WASMOON's WASM memory management doesn't handle rapid allocation/deallocation of large strings well. Each frame created ~10-20KB of JSON strings, and the heap couldn't keep up.

### Future: Revisiting WASM Lua

After the web engine stabilizes, we may revisit WASM-based Lua for performance:

1. **Reduce per-frame JSON size** - Only send changed entities
2. **Different WASM Lua** - Try other implementations (e.g., Moonshine, lua-wasm)
3. **Custom WASM build** - Tune memory settings, use larger initial heap
4. **Streaming updates** - Send incremental diffs instead of full state

For now, Fengari's correctness and stability outweigh WASMOON's potential performance gains.

## Remote Logging

The bridge includes WebSocket log streaming for debugging:

```javascript
// Enable via URL: ?logstream=true&logserver=ws://localhost:8001
let logSocket = new WebSocket(serverUrl);

function streamLog(level, source, message) {
    if (logSocket?.readyState === WebSocket.OPEN) {
        logSocket.send(JSON.stringify({ level, source, message }));
    }
}

// Console interception
console.log = function(...args) {
    originalConsoleLog.apply(console, args);
    streamLog('INFO', 'console', args.join(' '));
};
```

The log server (`games/browser/log_server.py`) writes timestamped logs to `data/logs/browser/`.

## Build Process

`games/browser/build.py` prepares the pygbag bundle:

1. **Copy Python files** - game_runtime.py, lua_bridge.py, etc.
2. **Copy fengari_bridge.js** - JavaScript Lua runtime
3. **Convert YAML → JSON** - PyYAML not available in WASM
4. **Copy Lua subroutines** - lua/behavior/*.lua, etc.
5. **Patch index.html** - Add early error handlers
6. **Run pygbag** - Compile to WASM

## File Reference

| File | Purpose |
|------|---------|
| `games/browser/fengari_bridge.js` | JavaScript Lua runtime and ams.* API |
| `games/browser/lua_bridge.py` | Python LuaEngineBrowser |
| `games/browser/game_runtime.py` | Browser game loop, message handling |
| `games/browser/main.py` | Entry point, pygame initialization |
| `games/browser/build.py` | Build script for pygbag |
| `games/browser/log_server.py` | WebSocket log streaming server |
| `games/browser/tests/test_fengari_bridge.mjs` | Unit tests for bridge logic |

## Key Design Principles

1. **Same GameEngine** - Browser uses identical GameEngine as native
2. **Bridge Pattern** - LuaEngineBrowser has same interface as LuaEngine
3. **Serialized State** - Full entity state sent each frame (for now)
4. **Crash on Error** - Lua errors immediately visible, not silently ignored
5. **Subroutines Stay in Lua** - No JS↔Lua function conversion
6. **Deferred Results** - Python polls for results, no blocking
