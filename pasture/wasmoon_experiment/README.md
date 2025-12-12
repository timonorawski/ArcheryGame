# WASMOON Experiment (Archived)

**Archived**: December 2024

## What This Was

An attempt to use WASMOON (Lua 5.4 compiled to WebAssembly) for browser-based
Lua execution in YAML games.

## Why It Failed

WASMOON has fundamental memory management issues when handling large strings:

1. **Memory corruption after ~1-2 seconds** - Processing 52 entities per frame
   with JSON state serialization caused "memory access out of bounds" errors

2. **`_ENV nil` errors** - Functions captured `_ENV` as upvalue, which became
   nil over time due to WASM memory corruption

3. **Both approaches failed**:
   - Embedding JSON in `doString()` code
   - Passing JSON via `global.set()`

## Replacement

Replaced with **Fengari** (pure JavaScript Lua 5.3 implementation):
- No WASM, no memory corruption
- Synchronous execution (like native Lupa)
- See `games/browser/fengari_bridge.js`

## Files

- `wasmoon_bridge.js` - Final v15 attempt with global.set() approach
- `wasmoon_bridge_v2.js` - Earlier version
- `wasmoon_test.html` - Browser test harness
- `wasmoon_test_node.mjs` - Node.js test script
