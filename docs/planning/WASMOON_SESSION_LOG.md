# WASMOON Bridge Development Session Log

**Date**: December 11-12, 2025
**Goal**: Get YAML-driven games (BrickBreakerNG) running in browser via pygbag with WASMOON Lua support

## Context

WASMOON is Lua 5.4 compiled to WebAssembly. We're using it to run Lua behavior scripts in the browser for our YAML game engine. The Python game engine runs via pygbag (Python-to-WASM), and communicates with WASMOON via window.postMessage.

## What We Tried (Chronological)

### Attempt 1: Direct Function Calls
**Approach**: Define Lua functions, then call them directly from JavaScript using `luaEngine.global.get('funcName')()`.

**Result**: FAILED - WASMOON returns proxy objects, not callable functions. Direct invocation doesn't work as expected.

### Attempt 2: doString() for Everything
**Approach**: Use `luaEngine.doString(code)` to execute all Lua code, including function calls.

**Result**: PARTIAL SUCCESS - Code executes, but:
- `doString()` returns a **Promise**, not a synchronous result
- We initially missed this and got `[object Promise]` errors when trying to JSON.parse the result

### Attempt 3: Async/Await for doString()
**Approach**: Make all functions that call `doString()` async and await the results.

**Result**: PARTIAL SUCCESS - Async works, but then we hit environment issues.

### Attempt 4: Pure Lua AMS API (No JS Callbacks)
**Approach**: Instead of calling JS functions from Lua, implement the entire AMS API in pure Lua. Pass state via global tables, collect changes via JSON encoding.

**Result**: PARTIAL SUCCESS - The API loads, but functions defined in one `doString()` can't be called from another.

### Attempt 5: Understanding _ENV Issues
**Discovery**: Functions defined in a `doString()` chunk capture `_ENV` as an upvalue. When those functions are called from a DIFFERENT `doString()` chunk, `_ENV` is nil.

**Error seen**: `attempt to index a nil value (upvalue '_ENV')`

### Attempt 6: Using load() with Explicit Environment
**Approach**: Use Lua's `load(code, name, "t", env)` to compile code with an explicit environment table containing all needed globals.

**Result**: FAILED - `setmetatable` (needed to create the environment) is nil!

### Attempt 7: Capturing Globals as Upvalues
**Approach**: At AMS API initialization, capture all globals as local variables (upvalues) before defining functions:
```lua
do
    local _setmetatable = setmetatable
    local _load = load
    -- ... capture everything ...

    function _ams_load_subroutine(code, name)
        local env = _setmetatable({...}, {...})
        -- ...
    end
end
```

**Result**: FAILED - The captured `_setmetatable` is nil because `setmetatable` doesn't exist even at capture time!

### Attempt 8: Plain Table Environment (No Metatable)
**Approach**: Create environment as plain table without using `setmetatable`:
```lua
local env = {
    ams = _ams,
    print = _print,
    -- ...
}
local chunk = _load(code, name, "t", env)
```

**Result**: FAILED - `_load` (captured from `load`) is nil. Even basic Lua functions don't exist.

### Attempt 9: Diagnostic - What Globals Exist?
**Approach**: Created Node.js test rig (`wasmoon_test_node.mjs`) to test each global individually.

**Result**: SUCCESS - We were completely wrong about the sandbox!

## Key Discoveries (Dec 12, 2025 - Diagnostic Results)

### 1. WASMOON Sandbox is NOT Restrictive!

**We were wrong.** ALL standard Lua globals exist and work:

| Category | Status |
|----------|--------|
| Basic globals (print, type, pairs, ipairs, pcall, error, assert, etc.) | ✓ ALL EXIST |
| Table functions (setmetatable, getmetatable, rawget, rawset, rawequal, rawlen) | ✓ ALL EXIST |
| Code loading (load, loadfile, dofile) | ✓ ALL EXIST |
| Standard libraries (math, string, table, os, io, coroutine, debug, utf8, package) | ✓ ALL EXIST |
| `_G` and `_ENV` | ✓ BOTH EXIST as tables |

### 2. doString() Returns Promises
Every `luaEngine.doString()` call returns a Promise, not a synchronous value. Must use `await` or `.then()`.

### 3. Globals DO Persist Between doString() Calls!
Setting `_test_var = 12345` in one `doString()` and reading it in another: **WORKS PERFECTLY**.

### 4. Function _ENV Capture WORKS!
Defining a function that accesses a global in one `doString()`, then calling it from another: **WORKS PERFECTLY**.

### 5. Closures with Upvalues WORK!
Local variables captured as upvalues persist across `doString()` calls: **WORKS PERFECTLY**.

### 6. JS Function Injection WORKS!
Using `luaEngine.global.set('funcName', jsFunction)` and calling from Lua: **WORKS PERFECTLY**.

### 7. THE ACTUAL BUG: load() with Custom Environment!

The `_ENV` nil error happens **specifically** when using `load()` with a custom environment table:

```lua
-- THIS CAUSES THE _ENV NIL ERROR:
local env = { x = 42 }
local chunk = load("return x", "test", "t", env)
chunk()  -- ERROR: attempt to index a nil value (upvalue '_ENV')
```

This is the pattern we were using to sandbox behavior code, and it's what was breaking!

### Root Cause Analysis

Our bridge was using `load(code, name, "t", customEnv)` to run behavior code in a sandboxed environment. This pattern breaks `_ENV` in WASMOON. The code inside the loaded chunk tries to access `_ENV`, which is supposed to be the custom environment, but something in WASMOON's implementation causes it to be nil instead.

### Solution

**Don't use custom environments!** Instead:
1. Load behavior code directly with `load(code)` (no custom env)
2. Or use `doString(code)` directly
3. Code will run in the global environment where all globals work
4. Use global variables for the AMS API instead of trying to inject them via custom env

## Escaping Issues Discovered

### JavaScript -> Lua String Escaping
When embedding Lua code in JavaScript template strings:
- Backslashes need double-escaping: `\\\\` in JS becomes `\\` in the string
- For Lua patterns like `gsub('\\', '\\\\')`, the escaping becomes nightmarish

**Solution**: Use `string.char(N)` instead of escape sequences:
```lua
local bs = string.char(92)  -- backslash
escaped = str:gsub(bs, bs..bs)  -- replace \ with \\
```

## Architecture Attempts

### Message-Based Communication
```
Python (pygbag) <--postMessage--> JavaScript Bridge <--doString--> WASMOON Lua
```

Message types:
- `lua_load_subroutine` - Load behavior/collision code
- `lua_update` - Per-frame update with entity state
- `lua_collision` - Handle collision events
- `lua_update_result` / `lua_collision_result` - Results back to Python

### State Passing Strategy
Instead of calling Lua functions with arguments:
1. Serialize state to JSON in JavaScript
2. Pass JSON string to Lua: `_ams_set_gamestate_json('{"x":1,...}')`
3. Lua parses JSON, updates internal state
4. After execution, Lua serializes changes to JSON
5. JavaScript retrieves JSON: `return _ams_get_statechanges_json()`

## Open Questions (RESOLVED)

1. **What globals ARE available in WASMOON?**
   - **ANSWER**: ALL of them! Standard Lua 5.4 environment is fully available.

2. **Can we use luaEngine.global.set() to inject globals?**
   - **ANSWER**: Yes! Works perfectly for both variables and functions.

3. **Is there a WASMOON configuration to enable more globals?**
   - **ANSWER**: Not needed - everything is already available.

4. **Alternative: fengari-web?**
   - **ANSWER**: Not needed - WASMOON works fine, we just used it wrong.

## Files Modified

- `games/browser/wasmoon_bridge.js` - Main bridge implementation
- `games/browser/build.py` - Build script with error handler injection
- `games/browser/log_server.py` - WebSocket log streaming server

## Test Rig Created

- `games/browser/wasmoon_test.html` - Browser-based interactive test rig
- `games/browser/wasmoon_test_node.mjs` - Node.js automated test rig

Test results (Dec 12, 2025): All tests pass except `load()` with custom environment.

## Next Steps (Updated Dec 12, 2025)

**Root cause identified!** The fix is straightforward:

1. **Remove custom environment from load()** - Stop using `load(code, name, "t", customEnv)`
2. **Simplify the bridge** - Since globals persist and functions work across `doString()` calls:
   - Define behavior code directly via `doString(behaviorCode)`
   - Store functions in global variables (they'll persist)
   - The AMS API can be defined once and used everywhere
3. **Test the simplified approach** - Run BrickBreakerNG with the fixed bridge

### Simplified Architecture

```
1. Initialize WASMOON
2. Define AMS API via doString() - creates global functions
3. For each behavior:
   - doString(behaviorCode) - creates global function _behavior_XXX()
4. Per-frame update:
   - Set gamestate via global.set('_ams_current_entity', {...})
   - Call behavior: doString('return _behavior_XXX()')
   - Read changes from returned table
```

No sandboxing, no custom environments, just global state.

## Resources

- WASMOON npm: https://www.npmjs.com/package/wasmoon
- WASMOON GitHub: https://github.com/ceifa/wasmoon
- Lua 5.4 manual: https://www.lua.org/manual/5.4/
