# YAMS Web Lua Debugger with Step-Back
**Project codename:** Yam Time Machine
**Status:** Design complete, implementation required
**Goal:** Let users step backward through code execution using rollback snapshots.

## 1. Core Concept

Use the existing rollback system (built for CV latency compensation) to enable time-travel debugging. When a user steps backward, restore a previous game snapshot and re-execute to the desired point.

## 2. Current System State

### What Exists

| Component | Status | Location |
|-----------|--------|----------|
| Fengari Lua runtime | Working | `games/browser/fengari_bridge.js` |
| Entity snapshots | Working | `ams/games/game_engine/rollback/snapshot.py` |
| Snapshot capture | Working | `RollbackStateManager.capture()` |
| Snapshot restore | Working | `RollbackStateManager.restore()` |
| Re-simulation | Working | `RollbackStateManager._resimulate()` |
| Monaco Editor | Working | `frontend/src/lib/ide/MonacoEditor.svelte` |
| Hot reload | Working | `PreviewFrame.svelte` postMessage |

### What Does NOT Exist

| Component | Notes |
|-----------|-------|
| Debug hooks | `debug` library removed from Fengari sandbox |
| Breakpoint manager | No infrastructure |
| Locals inspection | No `debug.getlocal()` wrapper |
| Call stack display | No `debug.getinfo()` wrapper |
| Execution position tracking | Snapshots don't include Lua line numbers |
| Step commands | No F10/F11/← handling |

### Architecture Reality Check

**Fengari sandbox** (`fengari_bridge.js:503-517`):
```javascript
function applySandbox() {
    doString(`
        io = nil
        os = nil
        loadfile = nil
        dofile = nil
        debug = nil      -- REMOVED for security
        package = nil
        require = nil
    `, 'sandbox');
}
```

The `debug` library is explicitly removed. To enable debugging, we need to:
1. Keep `debug` in a controlled manner (not exposed to user code)
2. Create wrapper functions that use `debug.sethook`, `debug.getlocal`, `debug.getinfo`

**Snapshot contents** (`snapshot.py`):
```python
@dataclass
class GameSnapshot:
    frame_number: int
    elapsed_time: float
    timestamp: float
    entities: Dict[str, EntitySnapshot]  # All entity state
    score: int
    lives: int
    internal_state: str
    scheduled_callbacks: Tuple[ScheduledCallbackSnapshot, ...]
```

Snapshots capture **game state** (entities, score, callbacks), NOT **Lua execution state** (call stack, locals, current line). After restoring a snapshot, Lua re-executes from the beginning of that frame.

## 3. Debug Hook Architecture

### Fengari Debug Hooks (New)

Add to `fengari_bridge.js`:

```javascript
// =========================================================================
// Debug Infrastructure (kept separate from user sandbox)
// =========================================================================

let debugEnabled = false;
let breakpoints = new Map();  // "filename:line" -> true
let debugState = 'RUNNING';   // RUNNING | PAUSED | STEPPING
let stepMode = null;          // null | 'into' | 'over' | 'out'
let currentFrame = { file: null, line: 0, func: null };
let callStack = [];
let pauseCallback = null;

// Keep debug library reference before sandbox removes it
let debugLib = null;

function initDebugger() {
    // Capture debug library before sandbox clears it
    debugLib = doString('return debug', 'get_debug');

    // Now apply sandbox (which sets debug = nil for user code)
    applySandbox();
}

function enableDebugging(callback) {
    debugEnabled = true;
    pauseCallback = callback;

    // Set line hook via preserved debug reference
    doString(`
        local debug_lib = ...  -- passed from JS
        debug_lib.sethook(function(event, line)
            __ams_debug_hook(event, line)
        end, "l")
    `, 'debug_hook_setup', debugLib);
}

function __ams_debug_hook(event, line) {
    if (!debugEnabled) return;

    // Get current file info
    const info = getDebugInfo(2);  // Caller's frame
    currentFrame = {
        file: info.source,
        line: line,
        func: info.name || 'anonymous'
    };

    // Check breakpoint
    const key = `${info.source}:${line}`;
    const shouldPause = breakpoints.has(key) ||
                        stepMode === 'into' ||
                        (stepMode === 'over' && callStack.length <= stepTargetDepth);

    if (shouldPause) {
        debugState = 'PAUSED';
        stepMode = null;

        // Collect locals
        const locals = collectLocals();

        // Notify UI
        if (pauseCallback) {
            pauseCallback({
                type: 'paused',
                file: info.source,
                line: line,
                func: info.name,
                locals: locals,
                callStack: buildCallStack()
            });
        }

        // Block until resume (this is tricky in browser - see implementation notes)
    }
}

function getDebugInfo(level) {
    // Use preserved debug library
    return doString(`
        local debug_lib, level = ...
        return debug_lib.getinfo(level, "nSl")
    `, 'debug_getinfo', debugLib, level);
}

function collectLocals() {
    const locals = {};
    let i = 1;
    while (true) {
        const result = doString(`
            local debug_lib, level, i = ...
            local name, value = debug_lib.getlocal(level, i)
            if name then
                return {name = name, value = tostring(value)}
            end
            return nil
        `, 'debug_getlocal', debugLib, 3, i);

        if (!result) break;
        locals[result.name] = result.value;
        i++;
    }
    return locals;
}
```

### Breakpoint Manager

```javascript
// In fengari_bridge.js
function setBreakpoint(file, line) {
    breakpoints.set(`${file}:${line}`, true);
}

function clearBreakpoint(file, line) {
    breakpoints.delete(`${file}:${line}`);
}

function clearAllBreakpoints() {
    breakpoints.clear();
}

// Step commands
function stepInto() {
    stepMode = 'into';
    debugState = 'RUNNING';
    // Resume execution
}

function stepOver() {
    stepMode = 'over';
    stepTargetDepth = callStack.length;
    debugState = 'RUNNING';
}

function stepOut() {
    stepMode = 'out';
    stepTargetDepth = callStack.length - 1;
    debugState = 'RUNNING';
}

function continueExecution() {
    stepMode = null;
    debugState = 'RUNNING';
}
```

## 4. Step-Backward Implementation

Step-backward uses existing rollback infrastructure:

```javascript
// In the game iframe (pygbag context)
let frameHistory = [];  // Track frame numbers with debug info
let currentHistoryIndex = -1;

function captureDebugFrame(frameNumber, debugState) {
    frameHistory.push({
        frame: frameNumber,
        file: debugState.file,
        line: debugState.line,
        locals: debugState.locals
    });
    currentHistoryIndex = frameHistory.length - 1;

    // Limit history
    if (frameHistory.length > 120) {  // 2 seconds at 60fps
        frameHistory.shift();
        currentHistoryIndex--;
    }
}

function stepBackward() {
    if (currentHistoryIndex <= 0) {
        notifyUI({ type: 'error', message: 'No earlier state available' });
        return;
    }

    currentHistoryIndex--;
    const target = frameHistory[currentHistoryIndex];

    // Use rollback system to restore game state
    // This requires Python-side call
    postMessage({
        type: 'rollback_to_frame',
        frame: target.frame
    });

    // After restore, re-run with debugging to reach exact line
    // (This is the complex part - see implementation notes)
}
```

### Python Integration

```python
# In game_runtime.py or similar
def handle_rollback_to_frame(frame_number: int) -> None:
    """Handle debug step-backward request."""
    if not rollback_manager:
        return

    # Find snapshot at or before target frame
    snapshot = rollback_manager.find_snapshot_by_frame(frame_number)
    if not snapshot:
        return

    # Restore game state
    rollback_manager.restore(game_engine, snapshot)

    # Notify JS that state is restored
    # JS will then re-execute behaviors with debug hooks
    # to pause at the same position
```

## 5. Execution Position Tracking

The key challenge: snapshots restore **game state** but Lua re-executes from scratch. To pause at the same line after rollback:

**Option A: Re-execute with line counting**
```javascript
// After rollback restore, we know target was "gravity.lua:15"
// Set a one-shot breakpoint there
function stepBackwardTo(file, line) {
    // Restore snapshot
    restoreSnapshot(targetFrame);

    // Set temporary breakpoint
    const tempKey = `${file}:${line}`;
    breakpoints.set(tempKey, { oneShot: true });

    // Run frame - will pause at that line
    runFrame();
}
```

**Option B: Track execution trace per frame**
```javascript
// Store execution trace with each frame
let executionTrace = [];  // [{file, line}, {file, line}, ...]

function __ams_debug_hook(event, line) {
    // Record every line executed
    const info = getDebugInfo(2);
    executionTrace.push({ file: info.source, line: line });

    // ... rest of breakpoint checking
}

function captureDebugFrame(frameNumber) {
    frameHistory.push({
        frame: frameNumber,
        trace: [...executionTrace]  // Copy trace
    });
    executionTrace = [];  // Reset for next frame
}

// Step backward = restore + replay trace to position N-1
```

## 6. UI Components

### DebugPanel.svelte

```svelte
<script>
  import { onMount } from 'svelte';

  export let wsConnection;
  export let monacoEditor;

  let debugState = 'STOPPED';  // STOPPED | RUNNING | PAUSED
  let currentFile = '';
  let currentLine = 0;
  let locals = {};
  let callStack = [];
  let breakpoints = new Map();

  function handleDebugMessage(msg) {
    switch (msg.type) {
      case 'paused':
        debugState = 'PAUSED';
        currentFile = msg.file;
        currentLine = msg.line;
        locals = msg.locals;
        callStack = msg.callStack;
        highlightLine(msg.file, msg.line);
        break;
      case 'running':
        debugState = 'RUNNING';
        clearHighlight();
        break;
    }
  }

  function highlightLine(file, line) {
    // Monaco decoration for current execution line
    monacoEditor.revealLineInCenter(line);
    monacoEditor.deltaDecorations([], [{
      range: new monaco.Range(line, 1, line, 1),
      options: {
        isWholeLine: true,
        className: 'debug-current-line',
        glyphMarginClassName: 'debug-arrow'
      }
    }]);
  }

  function toggleBreakpoint(line) {
    const key = `${currentFile}:${line}`;
    if (breakpoints.has(key)) {
      breakpoints.delete(key);
      sendCommand('clear_breakpoint', { file: currentFile, line });
    } else {
      breakpoints.set(key, true);
      sendCommand('set_breakpoint', { file: currentFile, line });
    }
  }

  function stepBackward() {
    sendCommand('step_backward');
  }

  function stepForward() {
    sendCommand('step_into');
  }

  function stepOver() {
    sendCommand('step_over');
  }

  function continueRun() {
    sendCommand('continue');
  }
</script>

<div class="debug-panel">
  <div class="toolbar">
    <button on:click={continueRun} disabled={debugState !== 'PAUSED'}>
      ▶ Continue (F5)
    </button>
    <button on:click={stepOver} disabled={debugState !== 'PAUSED'}>
      ⤵ Step Over (F10)
    </button>
    <button on:click={stepForward} disabled={debugState !== 'PAUSED'}>
      ↓ Step Into (F11)
    </button>
    <button on:click={stepBackward} disabled={debugState !== 'PAUSED'}>
      ← Step Back
    </button>
  </div>

  <div class="panels">
    <div class="locals-panel">
      <h3>Locals</h3>
      {#each Object.entries(locals) as [name, value]}
        <div class="local-var">
          <span class="name">{name}</span>
          <span class="value">{value}</span>
        </div>
      {/each}
    </div>

    <div class="callstack-panel">
      <h3>Call Stack</h3>
      {#each callStack as frame, i}
        <div class="stack-frame" class:current={i === 0}>
          {frame.func} ({frame.file}:{frame.line})
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .debug-panel { display: flex; flex-direction: column; height: 200px; }
  .toolbar { display: flex; gap: 8px; padding: 8px; border-bottom: 1px solid #333; }
  .panels { display: flex; flex: 1; overflow: hidden; }
  .locals-panel, .callstack-panel { flex: 1; overflow-y: auto; padding: 8px; }
  .local-var { display: flex; gap: 8px; font-family: monospace; }
  .name { color: #9cdcfe; }
  .value { color: #ce9178; }
  .stack-frame { padding: 4px; cursor: pointer; }
  .stack-frame:hover { background: #333; }
  .stack-frame.current { background: #264f78; }
</style>
```

### Monaco Breakpoint Integration

```javascript
// In MonacoEditor.svelte
function setupBreakpoints(editor) {
    editor.onMouseDown((e) => {
        if (e.target.type === monaco.editor.MouseTargetType.GUTTER_GLYPH_MARGIN) {
            const line = e.target.position.lineNumber;
            toggleBreakpoint(line);
        }
    });
}

function addBreakpointDecoration(line) {
    return editor.deltaDecorations([], [{
        range: new monaco.Range(line, 1, line, 1),
        options: {
            glyphMarginClassName: 'breakpoint-glyph',
            glyphMarginHoverMessage: { value: 'Breakpoint' }
        }
    }]);
}
```

## 7. Implementation Challenges

### Challenge 1: Blocking Execution in Browser

Lua `debug.sethook` expects synchronous pause, but browsers are async. Options:

**A. Busy-wait (not recommended)**
```javascript
while (debugState === 'PAUSED') {
    // Burns CPU, blocks UI
}
```

**B. Generator-based execution (recommended)**
```javascript
function* executeWithDebug(luaCode) {
    // Set hook that yields instead of blocking
    // Each step resumes the generator
}
```

**C. Web Worker isolation**
- Run Fengari in a Web Worker
- Use `Atomics.wait()` for true blocking
- Adds complexity but cleanest solution

### Challenge 2: Snapshot ↔ Debug Position Mapping

Snapshots don't store Lua execution position. Solutions:

1. **Frame-level granularity**: Step-back jumps to frame start, not exact line
2. **Execution trace recording**: Store line trace per frame (~1KB/frame overhead)
3. **Re-execution with counting**: After restore, count lines to reach position

### Challenge 3: Determinism

Rollback assumes deterministic execution. Debug hooks must not affect behavior:
- Don't modify game state in hooks
- Ensure same random seed after restore
- Handle time-based logic carefully

## 8. Implementation Steps

1. **Preserve debug library** - Modify sandbox to keep debug reference internally
2. **Add debug hook wrapper** - `__ams_debug_hook` function in fengari_bridge.js
3. **Implement breakpoint manager** - Set/clear/list breakpoints
4. **Add step commands** - into/over/out logic
5. **Create DebugPanel.svelte** - UI for controls, locals, call stack
6. **Monaco breakpoint gutter** - Click to toggle breakpoints
7. **Wire postMessage protocol** - Debug commands between iframe and parent
8. **Frame history tracking** - Record debug state per frame
9. **Step-backward via rollback** - Restore snapshot + re-execute to position

## 9. Message Protocol

```typescript
// Parent → Iframe (debug commands)
interface DebugCommand {
  type: 'debug_command';
  command: 'enable' | 'disable' | 'set_breakpoint' | 'clear_breakpoint' |
           'continue' | 'step_into' | 'step_over' | 'step_out' | 'step_backward';
  payload?: {
    file?: string;
    line?: number;
  };
}

// Iframe → Parent (debug events)
interface DebugEvent {
  type: 'debug_event';
  event: 'paused' | 'running' | 'error' | 'breakpoint_hit';
  data: {
    file?: string;
    line?: number;
    func?: string;
    locals?: Record<string, string>;
    callStack?: Array<{ file: string; line: number; func: string }>;
    error?: string;
  };
}
```

## 10. Testing Plan

1. **Unit tests for debug hooks** - Verify line counting, local collection
2. **Breakpoint tests** - Set, hit, clear, conditional
3. **Step tests** - into/over/out behavior
4. **Rollback integration** - Verify state restoration is correct
5. **UI tests** - Panel renders, Monaco integration works

## 11. Performance Considerations

- Debug hooks add ~1ms/frame overhead when enabled
- Execution trace storage: ~1KB/frame (120 frames = 120KB)
- Disable hooks when not debugging for zero overhead
- Limit history to 2 seconds (configurable)
