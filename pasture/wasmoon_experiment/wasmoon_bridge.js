/**
 * WASMOON Bridge for AMS Browser Games
 *
 * This module provides Lua 5.4 execution in the browser via WASMOON.
 * It communicates with Python (pygbag) via postMessage to execute
 * Lua behaviors and return state changes.
 *
 * Architecture:
 *   Python sends 'lua_*' messages -> wasmoonBridge processes them
 *   wasmoonBridge executes Lua with entity snapshot
 *   wasmoonBridge sends results back via 'lua_*_result' messages
 *
 * !! IMPORTANT - WASMOON GOTCHAS !!
 *
 * 1. NEVER call Lua functions directly from JavaScript! This causes:
 *      "TypeError: Cannot read properties of null (reading 'then')"
 *
 *    BAD:  behavior.on_update(entityId, dt)
 *    BAD:  action.execute(a, b, modifier)
 *    BAD:  typeof result.on_update === 'function'
 *
 *    GOOD: luaEngine.doString(`${globalName}.on_update("${entityId}", ${dt})`)
 *    GOOD: luaEngine.doString(`${globalName}.execute("${a}", "${b}", ${modifierLua})`)
 *
 *    Store Lua tables via global.get() for existence checks only, not property access.
 *
 * 2. Not all behaviors have all hooks! Check for nil before calling:
 *
 *    BAD:  luaEngine.doString(`${globalName}.on_update(...)`)
 *    GOOD: luaEngine.doString(`if ${globalName}.on_update then ${globalName}.on_update(...) end`)
 */

(function() {
    'use strict';

    // Version for debugging - update this when making changes
    const VERSION = 'v15 - pass JSON via global.set() not embedded string';

    // Global state
    let luaEngine = null;
    let luaReady = false;
    let luaCrashed = false;  // Once true, stop all Lua execution
    let subroutines = {
        behavior: {},
        collision_action: {},
        generator: {},
        input_action: {}
    };

    // Queue for subroutines sent before WASMOON is ready
    let pendingSubroutines = [];

    // Game state snapshot (updated each frame from Python)
    let gameState = {
        screenWidth: 800,
        screenHeight: 600,
        score: 0,
        elapsedTime: 0,
        entities: {}
    };

    // State changes to send back to Python
    let stateChanges = {
        entities: {},
        spawns: [],
        sounds: [],
        scheduled: [],
        score: 0
    };

    // Response queue for Python to poll
    window.luaResponses = window.luaResponses || [];

    // =========================================================================
    // Remote Log Streaming (for debugging)
    // =========================================================================
    // Enable via URL param: ?logstream=true or window.AMS_LOGSTREAM = true
    // Custom server: ?logserver=ws://host:port or window.AMS_LOGSERVER
    let logSocket = null;
    let logQueue = [];
    let buildId = 'unknown';
    let logStreamEnabled = false;

    function getLogConfig() {
        // Check URL params
        const params = new URLSearchParams(window.location.search);

        // Enable flag: ?logstream=true or ?logstream=1
        let enabled = params.get('logstream');
        if (enabled === null && typeof window.AMS_LOGSTREAM !== 'undefined') {
            enabled = window.AMS_LOGSTREAM;
        }
        logStreamEnabled = enabled === 'true' || enabled === '1' || enabled === true;

        // Server URL: ?logserver=ws://... or window.AMS_LOGSERVER
        let server = params.get('logserver');
        if (!server && typeof window.AMS_LOGSERVER !== 'undefined') {
            server = window.AMS_LOGSERVER;
        }
        return server || 'ws://localhost:8001';
    }

    function initLogStream() {
        const serverUrl = getLogConfig();

        if (!logStreamEnabled) {
            return; // Logging disabled
        }

        // Get build ID from the page if available
        if (window.AMS_BUILD_ID) {
            buildId = window.AMS_BUILD_ID;
        }

        // Try to connect to log server
        try {
            logSocket = new WebSocket(serverUrl);
            logSocket.onopen = () => {
                originalConsoleLog('[LogStream] Connected to', serverUrl);
                // Flush queued logs
                while (logQueue.length > 0) {
                    const entry = logQueue.shift();
                    logSocket.send(JSON.stringify(entry));
                }
            };
            logSocket.onclose = () => {
                originalConsoleLog('[LogStream] Disconnected');
                logSocket = null;
            };
            logSocket.onerror = () => {
                // Silent fail - log server may not be running
                logSocket = null;
            };
        } catch (e) {
            // WebSocket not available
        }
    }

    function streamLog(level, source, message) {
        if (!logStreamEnabled) return;

        const entry = {
            build_id: buildId,
            level: level,
            source: source,
            message: message,
        };

        if (logSocket && logSocket.readyState === WebSocket.OPEN) {
            logSocket.send(JSON.stringify(entry));
        } else {
            // Queue for later or just drop if queue is full
            if (logQueue.length < 100) {
                logQueue.push(entry);
            }
        }
    }

    // Save original console methods before any interception
    const originalConsoleLog = console.log;
    const originalConsoleWarn = console.warn;
    const originalConsoleError = console.error;

    function setupConsoleInterception() {
        if (!logStreamEnabled) return;

        console.log = function(...args) {
            originalConsoleLog.apply(console, args);
            streamLog('INFO', 'console', args.map(a => String(a)).join(' '));
        };
        console.warn = function(...args) {
            originalConsoleWarn.apply(console, args);
            streamLog('WARN', 'console', args.map(a => String(a)).join(' '));
        };
        console.error = function(...args) {
            originalConsoleError.apply(console, args);
            streamLog('ERROR', 'console', args.map(a => String(a)).join(' '));
        };
    }

    // Global error handlers - always capture, stream if enabled
    function setupGlobalErrorHandlers() {
        // Catch synchronous errors
        const originalOnError = window.onerror;
        window.onerror = function(message, source, lineno, colno, error) {
            const errorInfo = {
                message: String(message),
                source: source,
                line: lineno,
                col: colno,
                stack: error?.stack || 'no stack'
            };
            originalConsoleError('[GlobalError]', errorInfo);
            streamLog('ERROR', 'global_error', JSON.stringify(errorInfo));

            // Call original handler if exists
            if (originalOnError) {
                return originalOnError.apply(this, arguments);
            }
            return false;
        };

        // Catch unhandled promise rejections (like WASM errors)
        window.addEventListener('unhandledrejection', function(event) {
            const reason = event.reason;
            const errorInfo = {
                message: reason?.message || String(reason),
                stack: reason?.stack || 'no stack',
                type: reason?.name || 'UnhandledRejection'
            };
            originalConsoleError('[UnhandledRejection]', errorInfo);
            streamLog('ERROR', 'unhandled_rejection', JSON.stringify(errorInfo));
        });

        // Catch errors from WASM specifically
        window.addEventListener('error', function(event) {
            if (event.message?.includes('wasm') || event.filename?.includes('wasm')) {
                const errorInfo = {
                    message: event.message,
                    filename: event.filename,
                    lineno: event.lineno,
                    colno: event.colno,
                    type: 'WASMError'
                };
                originalConsoleError('[WASMError]', errorInfo);
                streamLog('ERROR', 'wasm_error', JSON.stringify(errorInfo));
            }
        });
    }

    // Initialize log stream on load
    if (typeof window !== 'undefined') {
        getLogConfig(); // Sets logStreamEnabled
        setupGlobalErrorHandlers(); // Always capture errors
        if (logStreamEnabled) {
            setupConsoleInterception();
            initLogStream();
        }

        // Expose streamLog globally for early error handlers (injected into index.html)
        window.AMS_streamLog = streamLog;

        // Process any early errors captured before wasmoon_bridge loaded
        if (window.AMS_EARLY_ERRORS && window.AMS_EARLY_ERRORS.length > 0) {
            console.log(`[WASMOON] Processing ${window.AMS_EARLY_ERRORS.length} early errors`);
            window.AMS_EARLY_ERRORS.forEach(function(err) {
                streamLog('ERROR', 'early_' + err.type, JSON.stringify(err));
            });
        }
    }

    /**
     * Load WASMOON library dynamically
     */
    async function loadWasmoonLibrary() {
        // Check if already loaded
        if (typeof LuaFactory !== 'undefined') {
            return true;
        }

        console.log('[WASMOON] Loading library from jsdelivr...');

        return new Promise((resolve, reject) => {
            // Use dynamic import for ES module
            const script = document.createElement('script');
            script.type = 'module';
            script.textContent = `
                import wasmoon from 'https://cdn.jsdelivr.net/npm/wasmoon@1.16.0/+esm';
                window.LuaFactory = wasmoon.LuaFactory;
                window.wasmoonLoaded = true;
                console.log('[WASMOON] Library loaded via jsdelivr ESM');
            `;
            script.onerror = (e) => reject(e);
            document.head.appendChild(script);

            // Poll for load completion
            let attempts = 0;
            const checkLoaded = setInterval(() => {
                attempts++;
                if (window.wasmoonLoaded || typeof window.LuaFactory !== 'undefined') {
                    clearInterval(checkLoaded);
                    resolve(true);
                } else if (attempts > 50) {  // 5 seconds timeout
                    clearInterval(checkLoaded);
                    reject(new Error('WASMOON load timeout'));
                }
            }, 100);
        });
    }

    /**
     * Initialize WASMOON
     */
    async function initWasmoon() {
        if (luaEngine) return;

        console.log('[WASMOON] Initializing...');

        try {
            // Load wasmoon library if not already loaded
            await loadWasmoonLibrary();

            if (typeof LuaFactory === 'undefined') {
                console.error('[WASMOON] LuaFactory not found after load attempt.');
                return;
            }

            const factory = new LuaFactory();
            luaEngine = await factory.createEngine();

            // Apply sandbox
            applySandbox();

            // Register ams.* API
            registerAmsApi();

            luaReady = true;
            console.log('[WASMOON] Ready');

            // Process any queued subroutines - SEQUENTIALLY to avoid VM corruption
            if (pendingSubroutines.length > 0) {
                console.log(`[WASMOON] Processing ${pendingSubroutines.length} queued subroutines`);
                for (const pending of pendingSubroutines) {
                    await loadSubroutine(pending.subType, pending.name, pending.code);
                }
                pendingSubroutines = [];
            }

        } catch (err) {
            console.error('[WASMOON] Init error:', err);
        }
    }

    /**
     * Apply Lua sandbox (light touch)
     *
     * In a browser context, the JavaScript/WASM VM already provides strong
     * sandboxing - there's no real filesystem, network access is CORS-limited,
     * etc. So we only need to disable things that could cause confusing errors
     * or are genuinely useless in the browser context.
     *
     * We keep ALL table/metatable functions (setmetatable, rawget, etc.)
     * because they're needed for normal Lua operation and don't pose risks.
     */
    function applySandbox() {
        luaEngine.doString(`
            -- Disable functions that don't make sense in browser context
            io = nil        -- no filesystem
            os = nil        -- no OS access
            loadfile = nil  -- no filesystem
            dofile = nil    -- no filesystem

            -- Keep debug.traceback for error reporting, disable other debug functions
            if debug then
                debug.debug = nil
                debug.setlocal = nil
                debug.setupvalue = nil
                debug.setmetatable = nil
                debug.sethook = nil
                -- Keep: debug.traceback, debug.getinfo (useful for error reporting)
            end

            -- Package system won't work without filesystem
            package = nil
            require = nil

            -- Limit string.dump (serializes bytecode, not useful here)
            string.dump = nil
        `);
    }

    /**
     * Register ams.* API - PURE LUA IMPLEMENTATION
     *
     * !! CRITICAL: Cannot use JavaScript functions from Lua in WASMOON !!
     * All AMS API functions are implemented in pure Lua.
     * State is passed via global tables, changes collected via JSON encoding.
     */
    function registerAmsApi() {
        // Define the entire AMS API in pure Lua
        const amsLuaCode = `
-- AMS API for WASMOON Browser Runtime
-- Pure Lua implementation - no JavaScript function calls

-- Global state tables (set by JavaScript before each frame)
_ams_gamestate = _ams_gamestate or {
    screenWidth = 800,
    screenHeight = 600,
    score = 0,
    elapsedTime = 0,
    entities = {}
}

-- Changes table (read by JavaScript after each frame)
_ams_statechanges = {
    entities = {},
    spawns = {},
    sounds = {},
    scheduled = {},
    score = 0
}

-- Spawn counter for unique IDs
_ams_spawn_counter = _ams_spawn_counter or 0

-- AMS API table (global, not local, to avoid _G issues in sandbox)
ams = ams or {}

-- Helper to get entity
local function getEntity(id)
    return _ams_gamestate.entities and _ams_gamestate.entities[id]
end

-- Helper to record entity change
local function setEntityProp(id, prop, value)
    if not _ams_statechanges.entities[id] then
        _ams_statechanges.entities[id] = {}
    end
    _ams_statechanges.entities[id][prop] = value
    -- Also update local for subsequent reads in same frame
    local e = getEntity(id)
    if e then e[prop] = value end
end

-- Transform API
function ams.get_x(id) local e = getEntity(id); return e and e.x or 0 end
function ams.set_x(id, x) setEntityProp(id, 'x', x) end
function ams.get_y(id) local e = getEntity(id); return e and e.y or 0 end
function ams.set_y(id, y) setEntityProp(id, 'y', y) end
function ams.get_vx(id) local e = getEntity(id); return e and e.vx or 0 end
function ams.set_vx(id, vx) setEntityProp(id, 'vx', vx) end
function ams.get_vy(id) local e = getEntity(id); return e and e.vy or 0 end
function ams.set_vy(id, vy) setEntityProp(id, 'vy', vy) end
function ams.get_width(id) local e = getEntity(id); return e and e.width or 0 end
function ams.get_height(id) local e = getEntity(id); return e and e.height or 0 end

-- Visual API
function ams.get_sprite(id) local e = getEntity(id); return e and e.sprite or '' end
function ams.set_sprite(id, s) setEntityProp(id, 'sprite', s) end
function ams.get_color(id) local e = getEntity(id); return e and e.color or 'white' end
function ams.set_color(id, c) setEntityProp(id, 'color', c) end
function ams.set_visible(id, v) setEntityProp(id, 'visible', v) end

-- State API
function ams.get_health(id) local e = getEntity(id); return e and e.health or 0 end
function ams.set_health(id, h) setEntityProp(id, 'health', h) end
function ams.is_alive(id) local e = getEntity(id); return e and e.alive or false end
function ams.destroy(id) setEntityProp(id, 'alive', false) end

-- Properties API
function ams.get_prop(id, key)
    local e = getEntity(id)
    if e and e.properties then
        return e.properties[key]
    end
    return nil
end

function ams.set_prop(id, key, value)
    if not _ams_statechanges.entities[id] then
        _ams_statechanges.entities[id] = { properties = {} }
    end
    if not _ams_statechanges.entities[id].properties then
        _ams_statechanges.entities[id].properties = {}
    end
    _ams_statechanges.entities[id].properties[key] = value
    -- Update local
    local e = getEntity(id)
    if e then
        if not e.properties then e.properties = {} end
        e.properties[key] = value
    end
end

function ams.get_config(id, behavior, key, defaultValue)
    local e = getEntity(id)
    if e and e.behavior_config and e.behavior_config[behavior] then
        local val = e.behavior_config[behavior][key]
        if val ~= nil then return val end
    end
    return defaultValue
end

-- Query API
function ams.get_entities_of_type(entityType)
    local result = {}
    for id, entity in pairs(_ams_gamestate.entities or {}) do
        if entity.alive and entity.entity_type == entityType then
            table.insert(result, id)
        end
    end
    return result
end

function ams.get_entities_by_tag(tag)
    local result = {}
    for id, entity in pairs(_ams_gamestate.entities or {}) do
        if entity.alive and entity.tags then
            for _, t in ipairs(entity.tags) do
                if t == tag then
                    table.insert(result, id)
                    break
                end
            end
        end
    end
    return result
end

function ams.count_entities_by_tag(tag)
    return #ams.get_entities_by_tag(tag)
end

function ams.get_all_entity_ids()
    local result = {}
    for id, entity in pairs(_ams_gamestate.entities or {}) do
        if entity.alive then
            table.insert(result, id)
        end
    end
    return result
end

-- Game state API
function ams.get_screen_width() return _ams_gamestate.screenWidth end
function ams.get_screen_height() return _ams_gamestate.screenHeight end
function ams.get_score() return _ams_statechanges.score end
function ams.add_score(points) _ams_statechanges.score = _ams_statechanges.score + points end
function ams.get_time() return _ams_gamestate.elapsedTime end

-- Events API
function ams.play_sound(soundName)
    table.insert(_ams_statechanges.sounds, soundName)
end

function ams.schedule(delay, callbackName, entityId)
    table.insert(_ams_statechanges.scheduled, {
        delay = delay,
        callback = callbackName,
        entity_id = entityId
    })
end

-- Spawning API
function ams.spawn(entityType, x, y, vx, vy, width, height, color, sprite)
    _ams_spawn_counter = _ams_spawn_counter + 1
    local spawnId = 'spawn_' .. _ams_spawn_counter
    table.insert(_ams_statechanges.spawns, {
        id = spawnId,
        entity_type = entityType,
        x = x or 0,
        y = y or 0,
        vx = vx or 0,
        vy = vy or 0,
        width = width or 0,
        height = height or 0,
        color = color or '',
        sprite = sprite or ''
    })
    return spawnId
end

-- Parent-child API
function ams.get_parent_id(id) local e = getEntity(id); return e and e.parent_id or '' end
function ams.has_parent(id) local e = getEntity(id); return e and e.parent_id and e.parent_id ~= '' end
function ams.get_children(id) local e = getEntity(id); return e and e.children or {} end

function ams.set_parent(childId, parentId, offsetX, offsetY)
    setEntityProp(childId, 'parent_id', parentId)
    setEntityProp(childId, 'parent_offset', {offsetX or 0, offsetY or 0})
end

function ams.detach_from_parent(id)
    setEntityProp(id, 'parent_id', nil)
    setEntityProp(id, 'parent_offset', {0, 0})
end

-- Math helpers (Lua stdlib)
ams.sin = math.sin
ams.cos = math.cos
ams.sqrt = math.sqrt
ams.atan2 = math.atan2
ams.abs = math.abs
ams.min = math.min
ams.max = math.max
ams.floor = math.floor
ams.ceil = math.ceil
ams.random = math.random

function ams.random_range(minVal, maxVal)
    return minVal + math.random() * (maxVal - minVal)
end

function ams.clamp(value, minVal, maxVal)
    return math.max(minVal, math.min(maxVal, value))
end

-- Debug (just prints, no streaming)
function ams.log(msg)
    print('[Lua]', msg)
end

-- =============================================================================
-- INTERNAL HELPER FUNCTIONS (used by JavaScript bridge)
-- Must be defined here as globals because local functions in doString have nil _ENV
-- =============================================================================

-- JSON encoder (global function so _ENV works)
function _ams_toJson(val)
    if val == nil then return 'null' end
    local t = type(val)
    if t == 'boolean' then return val and 'true' or 'false' end
    if t == 'number' then return tostring(val) end
    if t == 'string' then
        -- Escape special chars using character codes to avoid JS/Lua escaping issues
        local bs = string.char(92) -- backslash
        local escaped = val
        escaped = escaped:gsub(bs, bs..bs)       -- \\ -> \\\\
        escaped = escaped:gsub('"', bs..'"')     -- " -> \\"
        escaped = escaped:gsub(string.char(10), bs..'n')  -- newline -> \\n
        escaped = escaped:gsub(string.char(13), bs..'r')  -- carriage return -> \\r
        escaped = escaped:gsub(string.char(9), bs..'t')   -- tab -> \\t
        return '"' .. escaped .. '"'
    end
    if t == 'table' then
        -- Check if array (sequential integer keys starting at 1)
        local isArray = true
        local maxIdx = 0
        for k, _ in pairs(val) do
            if type(k) ~= 'number' or k ~= math.floor(k) or k < 1 then
                isArray = false
                break
            end
            maxIdx = math.max(maxIdx, k)
        end
        if isArray and maxIdx > 0 then
            local items = {}
            for i = 1, maxIdx do
                items[i] = _ams_toJson(val[i])
            end
            return '[' .. table.concat(items, ',') .. ']'
        else
            -- Object
            local pairs_arr = {}
            for k, v in pairs(val) do
                local key = type(k) == 'string' and k or tostring(k)
                table.insert(pairs_arr, '"' .. key .. '":' .. _ams_toJson(v))
            end
            return '{' .. table.concat(pairs_arr, ',') .. '}'
        end
    end
    return 'null'
end

-- Reset state changes (global function)
function _ams_reset_statechanges()
    _ams_statechanges = {
        entities = {},
        spawns = {},
        sounds = {},
        scheduled = {},
        score = 0
    }
end

-- Get state changes as JSON string (global function)
function _ams_get_statechanges_json()
    return _ams_toJson(_ams_statechanges)
end

-- Set game state from JSON string (global function)
-- This avoids _ENV issues by having the JSON parser defined at init time
function _ams_set_gamestate_json(jsonStr)
    -- Simple JSON parser for gamestate
    -- Note: This is a minimal parser for our specific use case
    local val, pos = _ams_parseJson(jsonStr, 1)
    if val then
        _ams_gamestate = val
        return true
    end
    return false
end

-- Simple JSON parser (global function)
function _ams_parseJson(str, pos)
    pos = pos or 1
    -- Skip whitespace
    while pos <= #str and str:sub(pos, pos):match('%s') do pos = pos + 1 end
    if pos > #str then return nil, pos end

    local c = str:sub(pos, pos)

    -- String
    if c == '"' then
        local endPos = pos + 1
        local bs = string.char(92) -- backslash
        while endPos <= #str do
            local ch = str:sub(endPos, endPos)
            if ch == '"' then
                local s = str:sub(pos + 1, endPos - 1)
                -- Unescape using character codes
                s = s:gsub(bs..bs, bs)                        -- \\\\ -> \\
                s = s:gsub(bs..'"', '"')                      -- \\" -> "
                s = s:gsub(bs..'n', string.char(10))          -- \\n -> newline
                s = s:gsub(bs..'r', string.char(13))          -- \\r -> carriage return
                s = s:gsub(bs..'t', string.char(9))           -- \\t -> tab
                return s, endPos + 1
            elseif ch == bs then
                endPos = endPos + 2
            else
                endPos = endPos + 1
            end
        end
        return nil, pos
    end

    -- Number
    if c:match('[%-0-9]') then
        local endPos = pos
        while endPos <= #str and str:sub(endPos, endPos):match('[0-9%.eE%+%-]') do
            endPos = endPos + 1
        end
        return tonumber(str:sub(pos, endPos - 1)), endPos
    end

    -- true/false/null
    if str:sub(pos, pos + 3) == 'true' then return true, pos + 4 end
    if str:sub(pos, pos + 4) == 'false' then return false, pos + 5 end
    if str:sub(pos, pos + 3) == 'null' then return nil, pos + 4 end

    -- Array
    if c == '[' then
        local arr = {}
        pos = pos + 1
        while pos <= #str do
            while pos <= #str and str:sub(pos, pos):match('%s') do pos = pos + 1 end
            if str:sub(pos, pos) == ']' then return arr, pos + 1 end
            local val
            val, pos = _ams_parseJson(str, pos)
            if val ~= nil then table.insert(arr, val) end
            while pos <= #str and str:sub(pos, pos):match('[%s,]') do pos = pos + 1 end
        end
        return arr, pos
    end

    -- Object
    if c == '{' then
        local obj = {}
        pos = pos + 1
        while pos <= #str do
            while pos <= #str and str:sub(pos, pos):match('%s') do pos = pos + 1 end
            if str:sub(pos, pos) == '}' then return obj, pos + 1 end
            -- Key
            local key
            key, pos = _ams_parseJson(str, pos)
            if type(key) ~= 'string' then return obj, pos end
            -- Colon
            while pos <= #str and str:sub(pos, pos):match('[%s:]') do pos = pos + 1 end
            -- Value
            local val
            val, pos = _ams_parseJson(str, pos)
            obj[key] = val
            while pos <= #str and str:sub(pos, pos):match('[%s,]') do pos = pos + 1 end
        end
        return obj, pos
    end

    return nil, pos
end

-- Set single entity in gamestate (for efficient updates)
function _ams_set_entity_json(entityId, jsonStr)
    local val = _ams_parseJson(jsonStr, 1)
    if val then
        _ams_gamestate.entities[entityId] = val
        return true
    end
    return false
end

-- Load a subroutine from code string (global function)
-- SIMPLIFIED: Don't use custom environments! They break _ENV in WASMOON.
-- Instead, load code directly into the global environment where everything works.
function _ams_load_subroutine(codeStr, subroutineName)
    -- Load WITHOUT custom environment - code runs in global env where all globals work
    local chunk, err = load(codeStr, subroutineName, "t")
    if not chunk then
        error("Failed to load " .. subroutineName .. ": " .. (err or "unknown"))
    end
    return chunk()
end
`;

        // Execute the pure Lua AMS implementation
        try {
            luaEngine.doString(amsLuaCode);
            console.log('[WASMOON] Registered pure Lua AMS API');
        } catch (err) {
            console.error('[WASMOON] Failed to register AMS API:', err);
            streamLog('ERROR', 'ams_api_init', err.message || String(err));
        }
    }

    /**
     * Safe Lua execution wrapper - catches all errors and logs them
     * Returns null on error instead of throwing
     *
     * IMPORTANT: WASMOON doString returns a Promise! This function
     * handles both sync results and awaits Promises.
     *
     * CRASH BEHAVIOR: On first error, sets luaCrashed=true and all
     * subsequent calls return null immediately. This prevents hammering
     * an unstable VM with more requests.
     */
    async function safeLuaExecAsync(code, context) {
        if (luaCrashed) {
            return null;  // VM is dead, don't even try
        }
        if (!luaEngine) {
            console.warn('[WASMOON] safeLuaExecAsync: engine not ready');
            return null;
        }
        try {
            // Execute code directly - no wrapper to minimize memory pressure
            const result = luaEngine.doString(code);
            // Handle Promise if returned
            if (result && typeof result.then === 'function') {
                return await result;
            }
            return result;
        } catch (err) {
            const errMsg = err.message || String(err);

            console.error(`[WASMOON] FATAL Lua error in ${context}:`);
            console.error(errMsg);
            console.error('[WASMOON] VM crashed - stopping all Lua execution');
            console.error('[WASMOON] Code that failed:', code.substring(0, 500));

            streamLog('ERROR', 'lua_fatal', JSON.stringify({
                context: context,
                error: errMsg,
                code: code.substring(0, 200)
            }));
            luaCrashed = true;  // Stop all future execution
            // Notify Python to stop the game loop
            window.luaResponses.push(JSON.stringify({
                type: 'lua_crashed',
                data: { error: errMsg, context: context }
            }));
            return null;
        }
    }

    /**
     * Synchronous Lua execution - fire and forget, doesn't wait for result
     * Use this for operations where we don't need the return value
     *
     * CRASH BEHAVIOR: Same as safeLuaExecAsync - first error stops everything.
     */
    function safeLuaExec(code, context) {
        if (luaCrashed) {
            return null;  // VM is dead, don't even try
        }
        if (!luaEngine) {
            console.warn('[WASMOON] safeLuaExec: engine not ready');
            return null;
        }
        try {
            const result = luaEngine.doString(code);
            // If it returns a Promise, attach error handler but don't wait
            if (result && typeof result.then === 'function') {
                result.catch(err => {
                    const errMsg = err.message || String(err);
                    console.error(`[WASMOON] FATAL async Lua error in ${context}:`, errMsg);
                    console.error('[WASMOON] VM crashed - stopping all Lua execution');
                    streamLog('ERROR', 'lua_fatal_async', JSON.stringify({
                        context: context,
                        error: errMsg
                    }));
                    luaCrashed = true;
                    // Notify Python to stop the game loop
                    window.luaResponses.push(JSON.stringify({
                        type: 'lua_crashed',
                        data: { error: errMsg, context: context }
                    }));
                });
                return 'pending'; // Indicate async operation started
            }
            return result;
        } catch (err) {
            const errMsg = err.message || String(err);
            console.error(`[WASMOON] FATAL Lua error in ${context}:`, errMsg);
            console.error('[WASMOON] VM crashed - stopping all Lua execution');
            streamLog('ERROR', 'lua_fatal', JSON.stringify({
                context: context,
                error: errMsg,
                code: code.substring(0, 200)
            }));
            luaCrashed = true;
            // Notify Python to stop the game loop
            window.luaResponses.push(JSON.stringify({
                type: 'lua_crashed',
                data: { error: errMsg, context: context }
            }));
            return null;
        }
    }

    /**
     * Convert JavaScript game state to Lua table assignment code
     */
    function gameStateToLua(state) {
        function toLua(val) {
            if (val === null || val === undefined) return 'nil';
            if (typeof val === 'boolean') return val ? 'true' : 'false';
            if (typeof val === 'number') return isFinite(val) ? String(val) : '0';
            if (typeof val === 'string') return JSON.stringify(val);
            if (Array.isArray(val)) {
                const items = val.map(v => toLua(v)).join(', ');
                return `{${items}}`;
            }
            if (typeof val === 'object') {
                const pairs = Object.entries(val).map(([k, v]) => {
                    // Use bracket notation for keys that aren't valid identifiers
                    const key = /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(k) ? k : `["${k}"]`;
                    return `${key} = ${toLua(v)}`;
                }).join(', ');
                return `{${pairs}}`;
            }
            return 'nil';
        }
        return toLua(state);
    }

    /**
     * Reset state changes table in Lua - async to ensure completion
     */
    async function resetLuaStateChanges() {
        // Call global function defined in AMS API initialization
        await safeLuaExecAsync('_ams_reset_statechanges()', 'resetStateChanges');
    }

    /**
     * Get state changes from Lua (returns JSON string)
     * Returns a Promise because WASMOON doString is async
     */
    async function getLuaStateChangesJson() {
        // Call global function defined in AMS API initialization
        const result = await safeLuaExecAsync('return _ams_get_statechanges_json()', 'getStateChanges');
        return result || '{}';
    }

    /**
     * Load a Lua subroutine (behavior, collision_action, spawn_transform)
     *
     * WASMOON NOTES (Dec 2025 - after diagnostic investigation):
     * ----------------------------------------------------------
     * WASMOON provides a FULL Lua 5.4 environment. All standard globals work!
     *
     * Key gotchas:
     * 1. doString() returns Promises - all Lua execution is async
     * 2. Can't call Lua functions directly from JS - use doString() to invoke
     * 3. DO NOT use load(code, name, "t", customEnv) - custom environments
     *    break _ENV and cause "attempt to index nil value (upvalue '_ENV')"
     *
     * SOLUTION: Load code directly into the global environment using
     * load(code, name, "t") without the 4th env parameter.
     */
    /**
     * Load a subroutine - ASYNC to properly wait for doString to complete
     * CRITICAL: WASMOON doString returns Promises. We must await them
     * to avoid concurrent operations that corrupt the VM.
     */
    async function loadSubroutine(subType, name, code) {
        if (!luaReady) {
            // Queue for later processing when WASMOON is ready
            console.log(`[WASMOON] Queueing ${subType}/${name} (engine not ready)`);
            pendingSubroutines.push({ subType, name, code });
            return false;
        }

        // Use the global _ams_load_subroutine function which has proper access to globals
        const globalName = `__subroutine_${subType}_${name}`;

        // Escape the code for embedding in Lua string (use single quotes to avoid nested escaping)
        const escapedCode = code.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n');

        // Call global loader function that was defined during AMS API init
        const wrappedCode = `${globalName} = _ams_load_subroutine('${escapedCode}', '${subType}/${name}')`;

        // MUST await to ensure load completes before accessing the global
        const loadResult = await safeLuaExecAsync(wrappedCode, `load_${subType}_${name}`);
        if (loadResult === null && luaCrashed) {
            return false;
        }

        // Get the result from the global (this is safe, not calling Lua functions)
        try {
            const result = luaEngine.global.get(globalName);

            if (!result) {
                console.warn(`[WASMOON] ${subType}/${name} returned nil`);
                return false;
            }

            subroutines[subType][name] = result;
            console.log(`[WASMOON] Loaded ${subType}/${name}`);
            return true;
        } catch (err) {
            console.error(`[WASMOON] Error getting ${subType}/${name} global:`, err);
            streamLog('ERROR', 'load_subroutine', JSON.stringify({
                type: subType,
                name: name,
                error: err.message || String(err)
            }));
            return false;
        }
    }

    /**
     * Execute behavior updates for all entities
     * Returns a Promise because WASMOON doString is async
     *
     * OPTIMIZATION: Batches all behavior calls into a single doString to avoid
     * overwhelming WASMOON with 50+ calls per frame (was causing memory errors).
     */
    async function executeBehaviorUpdates(dt, entities) {
        if (luaCrashed) {
            return { entities: {}, spawns: [], sounds: [], scheduled: [], score: 0 };
        }
        if (!luaReady) {
            console.log('[WASMOON] executeBehaviorUpdates: not ready yet');
            return { entities: {}, spawns: [], sounds: [], scheduled: [], score: 0 };
        }

        // Validate dt to prevent Infinity/NaN crashes
        if (!Number.isFinite(dt) || dt < 0) {
            console.warn('[WASMOON] Invalid dt:', dt, '- using 0.016');
            dt = 0.016;
        }

        // Update JavaScript game state
        gameState.entities = entities;

        // Pass state via JSON - include everything in ONE call
        const stateJson = JSON.stringify({
            screenWidth: gameState.screenWidth,
            screenHeight: gameState.screenHeight,
            score: gameState.score,
            elapsedTime: gameState.elapsedTime,
            entities: entities
        });

        // Build list of entity/behavior pairs for Lua to iterate
        // This keeps the Lua code string constant-size regardless of entity count
        const updateList = [];
        let entitiesChecked = 0;
        let entitiesWithBehaviors = 0;

        for (const [entityId, entity] of Object.entries(entities)) {
            entitiesChecked++;
            if (!entity.alive || !entity.behaviors) continue;
            entitiesWithBehaviors++;

            for (const behaviorName of entity.behaviors) {
                if (!subroutines.behavior[behaviorName]) {
                    continue;
                }
                updateList.push({ entityId, behaviorName });
            }
        }

        if (updateList.length === 0) {
            return { entities: {}, spawns: [], sounds: [], scheduled: [], score: 0 };
        }

        // Build compact JSON list of updates: [["entityId","behaviorName"],...]
        const updatesJson = JSON.stringify(updateList.map(u => [u.entityId, u.behaviorName]));

        // NEW APPROACH: Pass data via global.set() instead of embedding in Lua string
        // This avoids the large string manipulation that may be causing memory issues
        try {
            luaEngine.global.set('_ams_pending_state', stateJson);
            luaEngine.global.set('_ams_pending_updates', updatesJson);
            luaEngine.global.set('_ams_pending_dt', dt);
        } catch (err) {
            console.error('[WASMOON] Error setting globals:', err);
            return { entities: {}, spawns: [], sounds: [], scheduled: [], score: 0 };
        }

        // Execute with CONSTANT-SIZE Lua code - no embedded JSON
        // The code reads from globals set above
        const batchedCode = `
            _G._ams_set_gamestate_json(_G._ams_pending_state)
            _G._ams_reset_statechanges()
            local updates = _G._ams_parseJson(_G._ams_pending_updates, 1)
            local dt = _G._ams_pending_dt
            for i, upd in _G.ipairs(updates) do
                local entityId, behaviorName = upd[1], upd[2]
                local globalName = "__subroutine_behavior_" .. behaviorName
                local b = _G[globalName]
                if b and b.on_update then
                    _G.pcall(b.on_update, entityId, dt)
                end
            end
            return _G._ams_get_statechanges_json()
        `;

        let result = { entities: {}, spawns: [], sounds: [], scheduled: [], score: 0 };
        try {
            const changesJson = await safeLuaExecAsync(batchedCode, 'batchedBehaviorUpdate');
            if (changesJson && changesJson !== 'null' && typeof changesJson === 'string') {
                result = JSON.parse(changesJson);
            }
        } catch (err) {
            console.error('[WASMOON] Error in batched behavior update:', err);
        }

        // Log occasionally to verify behaviors are running
        if (gameState.elapsedTime < 1.0 || Math.floor(gameState.elapsedTime) % 5 === 0) {
            const changedCount = Object.keys(result.entities || {}).length;
            console.log(`[WASMOON] Frame: ${entitiesChecked} entities, ${entitiesWithBehaviors} with behaviors, ${updateList.length} behaviors run, ${changedCount} changed`);
        }

        return result;
    }

    /**
     * Execute a collision action
     * Async because WASMOON doString returns Promise
     */
    async function executeCollisionAction(actionName, entityA, entityB, modifier) {
        const emptyResult = { entities: {}, spawns: [], sounds: [], scheduled: [], score: 0 };
        if (luaCrashed) return emptyResult;
        if (!luaReady) return emptyResult;

        // Check if collision action is loaded
        if (!subroutines.collision_action[actionName]) {
            console.warn(`[WASMOON] Collision action not found: ${actionName}`);
            return emptyResult;
        }

        // Update JavaScript state
        gameState.entities[entityA.id] = entityA;
        gameState.entities[entityB.id] = entityB;

        // Update Lua game state with collision entities (use JSON to avoid _ENV issues)
        // MUST await to prevent concurrent doString operations
        const entityAJson = JSON.stringify(entityA).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const entityBJson = JSON.stringify(entityB).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const setResult = await safeLuaExecAsync(`
            _ams_set_entity_json("${entityA.id}", '${entityAJson}')
            _ams_set_entity_json("${entityB.id}", '${entityBJson}')
        `, 'collisionSetEntities');
        if (setResult === null && luaCrashed) {
            return emptyResult;
        }

        // Reset Lua state changes - must await
        await resetLuaStateChanges();

        // WASMOON: Call Lua collision action - MUST await
        const globalName = `__subroutine_collision_action_${actionName}`;

        // Set up modifier via JSON (avoids _ENV issues with table literals)
        let modifierSetup = '_ams_temp_modifier = nil';
        if (modifier && typeof modifier === 'object') {
            const modifierJson = JSON.stringify(modifier).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
            modifierSetup = `_ams_temp_modifier = _ams_parseJson('${modifierJson}', 1)`;
        }

        const luaCode = `${modifierSetup}; local a = ${globalName}; if a and a.execute then a.execute("${entityA.id}", "${entityB.id}", _ams_temp_modifier) end`;
        const execResult = await safeLuaExecAsync(luaCode, `collision_${actionName}`);
        if (execResult === null && luaCrashed) {
            return emptyResult;
        }

        // Get changes and merge back (async)
        const changesJson = await getLuaStateChangesJson();
        if (changesJson && changesJson !== 'null' && changesJson !== '{}') {
            try {
                const changes = JSON.parse(changesJson);
                // Merge into main stateChanges
                Object.assign(stateChanges.entities, changes.entities || {});
                // Use Array.isArray check and convert if needed (Lua tables aren't JS arrays)
                if (changes.spawns) {
                    const spawns = Array.isArray(changes.spawns) ? changes.spawns : Object.values(changes.spawns);
                    stateChanges.spawns.push(...spawns);
                }
                if (changes.sounds) {
                    const sounds = Array.isArray(changes.sounds) ? changes.sounds : Object.values(changes.sounds);
                    stateChanges.sounds.push(...sounds);
                }
                if (changes.scheduled) {
                    const scheduled = Array.isArray(changes.scheduled) ? changes.scheduled : Object.values(changes.scheduled);
                    stateChanges.scheduled.push(...scheduled);
                }
                stateChanges.score += (changes.score || 0);
            } catch (parseErr) {
                console.error('[WASMOON] Error parsing collision changes:', parseErr);
            }
        }

        return stateChanges;
    }

    /**
     * Handle messages from Python
     */
    async function handlePythonMessage(event) {
        let msg;
        try {
            if (typeof event.data === 'string') {
                msg = JSON.parse(event.data);
            } else {
                msg = event.data;
            }
        } catch {
            return; // Not a JSON message
        }

        if (msg.source !== 'lua_engine') return;

        const { type, data } = msg;

        switch (type) {
            case 'lua_init':
                gameState.screenWidth = data.screen_width || 800;
                gameState.screenHeight = data.screen_height || 600;
                initWasmoon();
                break;

            case 'lua_load_subroutine':
                // MUST await to ensure load completes before next operation
                await loadSubroutine(data.sub_type, data.name, data.code);
                break;

            case 'lua_update':
                gameState.elapsedTime = data.elapsed_time || 0;
                gameState.score = data.score || 0;
                // Log first few updates to verify message flow
                if (gameState.elapsedTime < 0.5) {
                    console.log('[WASMOON] lua_update received, entities:', Object.keys(data.entities || {}).length);
                }
                console.log('[WASMOON] About to call executeBehaviorUpdates, luaReady=' + luaReady);
                let results;
                try {
                    results = await executeBehaviorUpdates(data.dt, data.entities);
                    console.log('[WASMOON] executeBehaviorUpdates returned:', results ? 'object' : 'null');
                } catch (err) {
                    console.error('[WASMOON] executeBehaviorUpdates ERROR:', err);
                    results = { entities: {}, spawns: [], sounds: [], scheduled: [], score: 0 };
                }

                // Send results back to Python
                window.luaResponses.push(JSON.stringify({
                    type: 'lua_update_result',
                    data: results
                }));
                break;

            case 'lua_collision':
                const collisionResult = await executeCollisionAction(
                    data.action,
                    data.entity_a,
                    data.entity_b,
                    data.modifier
                );

                // Send collision results back
                window.luaResponses.push(JSON.stringify({
                    type: 'lua_collision_result',
                    data: collisionResult
                }));
                break;

            case 'lua_set_global':
                if (luaReady) {
                    luaEngine.global.set(data.name, data.value);
                }
                break;
        }
    }

    // Listen for messages from Python
    window.addEventListener('message', handlePythonMessage);

    // Also set up for direct window access (pygbag uses this)
    window.wasmoonBridge = {
        init: initWasmoon,
        loadSubroutine,
        executeBehaviorUpdates,
        executeCollisionAction,
        isReady: () => luaReady,
        getGameState: () => gameState,
        getStateChanges: () => stateChanges
    };

    // Auto-init if WASMOON is already loaded
    if (typeof LuaFactory !== 'undefined') {
        initWasmoon();
    }

    console.log(`[WASMOON Bridge] Loaded ${VERSION}`);

    // Signal to Python that bridge is ready
    window.wasmoonBridgeReady = true;
})();
