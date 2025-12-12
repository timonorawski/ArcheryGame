/**
 * Fengari Bridge for AMS Browser Games
 *
 * Pure JavaScript Lua 5.3 runtime - no WASM, no memory corruption issues.
 * Based on the Python Lupa architecture in ams/lua/engine.py.
 *
 * Architecture:
 *   - Entity storage in JavaScript (mirrors Python's LuaEngine.entities)
 *   - ams.* API exposed as JavaScript functions callable from Lua
 *   - Subroutines loaded and called synchronously (like Lupa)
 *   - Python sends messages -> bridge executes Lua -> returns results
 */

(function() {
    'use strict';

    const VERSION = 'v3 - fix subroutine loading (keep in Lua)';

    // Fengari modules (set after library loads)
    let fengari = null;
    let lua = null;
    let lauxlib = null;
    let lualib = null;
    let interop = null;
    let L = null;  // Main Lua state

    // Engine state
    let luaReady = false;
    let luaCrashed = false;  // Set true on Lua error - stops all execution
    let luaCrashError = null;  // Store the error that caused the crash
    let subroutines = {
        behavior: {},
        collision_action: {},
        generator: {},
        input_action: {}
    };

    // Queue for subroutines sent before Fengari is ready
    let pendingSubroutines = [];

    // Entity storage (mirrors Python's LuaEngine.entities)
    let entities = {};

    // Game state
    let gameState = {
        screenWidth: 800,
        screenHeight: 600,
        score: 0,
        elapsedTime: 0
    };

    // State changes collected during Lua execution
    let stateChanges = {
        entities: {},
        spawns: [],
        sounds: [],
        scheduled: [],
        score: 0
    };

    // Spawn counter for unique IDs
    let spawnCounter = 0;

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

        // Catch unhandled promise rejections
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
    }

    // =========================================================================
    // Fengari Library Loading
    // =========================================================================

    async function loadFengariLibrary() {
        if (window.fengari) {
            return true;
        }

        console.log('[FENGARI] Loading fengari-web from CDN...');

        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/fengari-web@0.1.4/dist/fengari-web.js';
            script.onload = () => {
                console.log('[FENGARI] Library loaded');
                resolve(true);
            };
            script.onerror = (e) => reject(e);
            document.head.appendChild(script);
        });
    }

    // =========================================================================
    // Fengari Initialization
    // =========================================================================

    async function initFengari() {
        if (luaReady) return;

        console.log('[FENGARI] Initializing...');

        try {
            await loadFengariLibrary();

            // Get fengari modules from the global
            fengari = window.fengari;
            lua = fengari.lua;
            lauxlib = fengari.lauxlib;
            lualib = fengari.lualib;
            interop = fengari.interop;

            // Create new Lua state
            L = lauxlib.luaL_newstate();
            lualib.luaL_openlibs(L);

            // Apply sandbox
            applySandbox();

            // Register ams.* API
            registerAmsApi();

            luaReady = true;
            console.log('[FENGARI] Ready');

            // Process queued subroutines
            if (pendingSubroutines.length > 0) {
                console.log(`[FENGARI] Processing ${pendingSubroutines.length} queued subroutines`);
                for (const pending of pendingSubroutines) {
                    loadSubroutine(pending.subType, pending.name, pending.code);
                }
                pendingSubroutines = [];
            }

        } catch (err) {
            console.error('[FENGARI] Init error:', err);
            streamLog('ERROR', 'init', err.message || String(err));
        }
    }

    // =========================================================================
    // Lua Execution Helpers
    // =========================================================================

    /**
     * Notify Python that Lua has crashed - game should stop.
     */
    function notifyLuaCrash(error, context) {
        luaCrashed = true;
        luaCrashError = { error, context, timestamp: Date.now() };

        console.error(`[FENGARI] FATAL: Lua crashed in ${context}:`, error);
        streamLog('FATAL', 'lua_crash', JSON.stringify({ error, context }));

        // Notify Python via response queue
        window.luaResponses.push(JSON.stringify({
            type: 'lua_crashed',
            data: {
                error: String(error),
                context: context,
                message: `Lua execution stopped due to error in ${context}: ${error}`
            }
        }));
    }

    /**
     * Execute Lua code string. Returns result or null on error.
     * On error, sets luaCrashed=true and stops all future execution.
     */
    function doString(code, context) {
        // If already crashed, refuse to execute
        if (luaCrashed) {
            return null;
        }

        if (!L) {
            console.warn('[FENGARI] doString: not ready');
            return null;
        }

        try {
            // Load the code
            const status = lauxlib.luaL_loadstring(L, fengari.to_luastring(code));
            if (status !== lua.LUA_OK) {
                const err = lua.lua_tojsstring(L, -1);
                lua.lua_pop(L, 1);
                notifyLuaCrash(err, context);
                return null;
            }

            // Execute
            const callStatus = lua.lua_pcall(L, 0, 1, 0);
            if (callStatus !== lua.LUA_OK) {
                const err = lua.lua_tojsstring(L, -1);
                lua.lua_pop(L, 1);
                notifyLuaCrash(err, context);
                return null;
            }

            // Get result
            const result = getStackValue(-1);
            lua.lua_pop(L, 1);
            return result;

        } catch (err) {
            notifyLuaCrash(err.message || String(err), context);
            return null;
        }
    }

    /**
     * Get value from Lua stack as JavaScript value.
     */
    function getStackValue(idx) {
        const type = lua.lua_type(L, idx);

        switch (type) {
            case lua.LUA_TNIL:
                return null;
            case lua.LUA_TBOOLEAN:
                return lua.lua_toboolean(L, idx);
            case lua.LUA_TNUMBER:
                return lua.lua_tonumber(L, idx);
            case lua.LUA_TSTRING:
                return lua.lua_tojsstring(L, idx);
            case lua.LUA_TTABLE:
                return tableToJS(idx);
            case lua.LUA_TFUNCTION:
                // Functions stay in Lua - we don't need them in JS
                // Subroutines are stored as Lua globals and called via doString
                return '[Lua function]';
            default:
                return null;
        }
    }

    /**
     * Convert Lua table at stack index to JavaScript object/array.
     */
    function tableToJS(idx) {
        // Make index absolute
        if (idx < 0) idx = lua.lua_gettop(L) + idx + 1;

        // Check if array (sequential integer keys starting at 1)
        let isArray = true;
        let maxIdx = 0;

        lua.lua_pushnil(L);
        while (lua.lua_next(L, idx) !== 0) {
            const keyType = lua.lua_type(L, -2);
            if (keyType === lua.LUA_TNUMBER) {
                const k = lua.lua_tonumber(L, -2);
                if (k === Math.floor(k) && k >= 1) {
                    maxIdx = Math.max(maxIdx, k);
                } else {
                    isArray = false;
                }
            } else {
                isArray = false;
            }
            lua.lua_pop(L, 1);  // Pop value, keep key for next iteration
        }

        // Convert
        if (isArray && maxIdx > 0) {
            const arr = [];
            for (let i = 1; i <= maxIdx; i++) {
                lua.lua_rawgeti(L, idx, i);
                arr.push(getStackValue(-1));
                lua.lua_pop(L, 1);
            }
            return arr;
        } else {
            const obj = {};
            lua.lua_pushnil(L);
            while (lua.lua_next(L, idx) !== 0) {
                const keyType = lua.lua_type(L, -2);
                let key;
                if (keyType === lua.LUA_TSTRING) {
                    key = lua.lua_tojsstring(L, -2);
                } else if (keyType === lua.LUA_TNUMBER) {
                    key = String(lua.lua_tonumber(L, -2));
                } else {
                    lua.lua_pop(L, 1);
                    continue;
                }
                obj[key] = getStackValue(-1);
                lua.lua_pop(L, 1);
            }
            return obj;
        }
    }

    /**
     * Push JavaScript value onto Lua stack.
     */
    function pushValue(val) {
        if (val === null || val === undefined) {
            lua.lua_pushnil(L);
        } else if (typeof val === 'boolean') {
            lua.lua_pushboolean(L, val);
        } else if (typeof val === 'number') {
            lua.lua_pushnumber(L, val);
        } else if (typeof val === 'string') {
            lua.lua_pushstring(L, fengari.to_luastring(val));
        } else if (Array.isArray(val)) {
            lua.lua_createtable(L, val.length, 0);
            for (let i = 0; i < val.length; i++) {
                pushValue(val[i]);
                lua.lua_rawseti(L, -2, i + 1);  // 1-indexed
            }
        } else if (typeof val === 'object') {
            const keys = Object.keys(val);
            lua.lua_createtable(L, 0, keys.length);
            for (const k of keys) {
                lua.lua_pushstring(L, fengari.to_luastring(k));
                pushValue(val[k]);
                lua.lua_rawset(L, -3);
            }
        } else if (typeof val === 'function') {
            // Push JS function as Lua C function
            lua.lua_pushcfunction(L, (L) => {
                // Gather arguments from stack
                const nargs = lua.lua_gettop(L);
                const args = [];
                for (let i = 1; i <= nargs; i++) {
                    args.push(getStackValue(i));
                }
                // Call JS function
                const result = val(...args);
                // Push result
                if (result !== undefined) {
                    pushValue(result);
                    return 1;
                }
                return 0;
            });
        } else {
            lua.lua_pushnil(L);
        }
    }

    /**
     * Set global variable in Lua.
     */
    function setGlobal(name, value) {
        pushValue(value);
        lua.lua_setglobal(L, fengari.to_luastring(name));
    }

    /**
     * Get global variable from Lua.
     */
    function getGlobal(name) {
        lua.lua_getglobal(L, fengari.to_luastring(name));
        const val = getStackValue(-1);
        lua.lua_pop(L, 1);
        return val;
    }

    // =========================================================================
    // Sandbox
    // =========================================================================

    function applySandbox() {
        // Remove dangerous globals (like Python's approach)
        doString(`
            io = nil
            os = nil
            loadfile = nil
            dofile = nil
            debug = nil
            package = nil
            require = nil

            -- Keep: pairs, ipairs, type, tostring, tonumber, select,
            --       unpack, pcall, error, next, math, string, table
        `, 'sandbox');
    }

    // =========================================================================
    // AMS API (mirrors Python's GameLuaAPI)
    // =========================================================================

    function registerAmsApi() {
        // Create ams namespace table
        doString('ams = {}', 'ams_init');

        // Helper to get entity
        const getEntity = (id) => entities[id];

        // Helper to record entity change
        const setEntityProp = (id, prop, value) => {
            if (!stateChanges.entities[id]) {
                stateChanges.entities[id] = {};
            }
            stateChanges.entities[id][prop] = value;
            // Also update local for reads in same frame
            const e = getEntity(id);
            if (e) e[prop] = value;
        };

        // Register all API functions
        const api = {
            // Transform
            get_x: (id) => { const e = getEntity(id); return e ? e.x : 0; },
            get_y: (id) => { const e = getEntity(id); return e ? e.y : 0; },
            set_x: (id, x) => setEntityProp(id, 'x', x),
            set_y: (id, y) => setEntityProp(id, 'y', y),
            get_vx: (id) => { const e = getEntity(id); return e ? e.vx : 0; },
            get_vy: (id) => { const e = getEntity(id); return e ? e.vy : 0; },
            set_vx: (id, vx) => setEntityProp(id, 'vx', vx),
            set_vy: (id, vy) => setEntityProp(id, 'vy', vy),
            get_width: (id) => { const e = getEntity(id); return e ? e.width : 0; },
            get_height: (id) => { const e = getEntity(id); return e ? e.height : 0; },

            // Visual
            get_sprite: (id) => { const e = getEntity(id); return e ? e.sprite : ''; },
            set_sprite: (id, s) => setEntityProp(id, 'sprite', s),
            get_color: (id) => { const e = getEntity(id); return e ? e.color : 'white'; },
            set_color: (id, c) => setEntityProp(id, 'color', c),
            set_visible: (id, v) => setEntityProp(id, 'visible', v),

            // State
            get_health: (id) => { const e = getEntity(id); return e ? e.health : 0; },
            set_health: (id, h) => setEntityProp(id, 'health', h),
            is_alive: (id) => { const e = getEntity(id); return e ? e.alive : false; },
            destroy: (id) => setEntityProp(id, 'alive', false),

            // Properties
            get_prop: (id, key) => {
                const e = getEntity(id);
                return (e && e.properties) ? e.properties[key] : null;
            },
            set_prop: (id, key, value) => {
                if (!stateChanges.entities[id]) {
                    stateChanges.entities[id] = { properties: {} };
                }
                if (!stateChanges.entities[id].properties) {
                    stateChanges.entities[id].properties = {};
                }
                stateChanges.entities[id].properties[key] = value;
                const e = getEntity(id);
                if (e) {
                    if (!e.properties) e.properties = {};
                    e.properties[key] = value;
                }
            },
            get_config: (id, behavior, key, defaultValue) => {
                const e = getEntity(id);
                if (e && e.behavior_config && e.behavior_config[behavior]) {
                    const val = e.behavior_config[behavior][key];
                    return val !== undefined ? val : defaultValue;
                }
                return defaultValue;
            },

            // Queries
            get_entities_of_type: (entityType) => {
                const result = [];
                for (const [id, e] of Object.entries(entities)) {
                    if (e.alive && e.entity_type === entityType) {
                        result.push(id);
                    }
                }
                return result;
            },
            get_entities_by_tag: (tag) => {
                const result = [];
                for (const [id, e] of Object.entries(entities)) {
                    if (e.alive && e.tags && e.tags.includes(tag)) {
                        result.push(id);
                    }
                }
                return result;
            },
            count_entities_by_tag: (tag) => {
                let count = 0;
                for (const e of Object.values(entities)) {
                    if (e.alive && e.tags && e.tags.includes(tag)) {
                        count++;
                    }
                }
                return count;
            },
            get_all_entity_ids: () => {
                return Object.keys(entities).filter(id => entities[id].alive);
            },

            // Game state
            get_screen_width: () => gameState.screenWidth,
            get_screen_height: () => gameState.screenHeight,
            get_score: () => stateChanges.score,
            add_score: (points) => { stateChanges.score += points; },
            get_time: () => gameState.elapsedTime,

            // Events
            play_sound: (name) => { stateChanges.sounds.push(name); },
            schedule: (delay, callback, entityId) => {
                stateChanges.scheduled.push({ delay, callback, entity_id: entityId });
            },

            // Spawning
            spawn: (entityType, x, y, vx, vy, width, height, color, sprite) => {
                spawnCounter++;
                const spawnId = 'spawn_' + spawnCounter;
                stateChanges.spawns.push({
                    id: spawnId,
                    entity_type: entityType,
                    x: x || 0,
                    y: y || 0,
                    vx: vx || 0,
                    vy: vy || 0,
                    width: width || 0,
                    height: height || 0,
                    color: color || '',
                    sprite: sprite || ''
                });
                return spawnId;
            },

            // Parent-child
            get_parent_id: (id) => { const e = getEntity(id); return (e && e.parent_id) ? e.parent_id : ''; },
            has_parent: (id) => { const e = getEntity(id); return !!(e && e.parent_id); },
            get_children: (id) => { const e = getEntity(id); return (e && e.children) ? e.children : []; },
            set_parent: (childId, parentId, offsetX, offsetY) => {
                setEntityProp(childId, 'parent_id', parentId);
                setEntityProp(childId, 'parent_offset', [offsetX || 0, offsetY || 0]);
            },
            detach_from_parent: (id) => {
                setEntityProp(id, 'parent_id', null);
                setEntityProp(id, 'parent_offset', [0, 0]);
            },

            // Math (use Lua's math library, but also expose these)
            sin: Math.sin,
            cos: Math.cos,
            sqrt: Math.sqrt,
            atan2: Math.atan2,
            abs: Math.abs,
            min: Math.min,
            max: Math.max,
            floor: Math.floor,
            ceil: Math.ceil,
            random: Math.random,
            random_range: (min, max) => min + Math.random() * (max - min),
            clamp: (val, min, max) => Math.max(min, Math.min(max, val)),

            // Debug
            log: (msg) => { console.log('[Lua]', msg); }
        };

        // Register each function in ams namespace
        for (const [name, fn] of Object.entries(api)) {
            setGlobal('_ams_temp_fn', fn);
            doString(`ams.${name} = _ams_temp_fn`, `ams.${name}`);
        }
        doString('_ams_temp_fn = nil', 'cleanup');

        console.log('[FENGARI] Registered ams.* API');
    }

    // =========================================================================
    // State Management
    // =========================================================================

    function resetStateChanges() {
        stateChanges = {
            entities: {},
            spawns: [],
            sounds: [],
            scheduled: [],
            score: 0
        };
    }

    function updateEntities(newEntities) {
        entities = newEntities;
    }

    // =========================================================================
    // Subroutine Loading
    // =========================================================================

    function loadSubroutine(subType, name, code) {
        if (luaCrashed) {
            return false;
        }

        if (!luaReady) {
            console.log(`[FENGARI] Queueing ${subType}/${name}`);
            pendingSubroutines.push({ subType, name, code });
            return false;
        }

        // Store result directly in Lua global - don't convert to JS (loses functions!)
        const globalName = `__subroutine_${subType}_${name}`;

        // Wrap the code to assign result to global
        const wrappedCode = `${globalName} = (function() ${code} end)()`;

        const context = `load_${subType}_${name}`;

        try {
            const status = lauxlib.luaL_loadstring(L, fengari.to_luastring(wrappedCode));
            if (status !== lua.LUA_OK) {
                const err = lua.lua_tojsstring(L, -1);
                lua.lua_pop(L, 1);
                notifyLuaCrash(err, context);
                return false;
            }

            const callStatus = lua.lua_pcall(L, 0, 0, 0);  // 0 results - we assigned to global
            if (callStatus !== lua.LUA_OK) {
                const err = lua.lua_tojsstring(L, -1);
                lua.lua_pop(L, 1);
                notifyLuaCrash(err, context);
                return false;
            }

            // Verify it was set (check if global is not nil)
            lua.lua_getglobal(L, fengari.to_luastring(globalName));
            const resultType = lua.lua_type(L, -1);
            lua.lua_pop(L, 1);

            if (resultType === lua.LUA_TNIL) {
                console.warn(`[FENGARI] ${subType}/${name} returned nil`);
                return false;
            }

            subroutines[subType][name] = globalName;
            console.log(`[FENGARI] Loaded ${subType}/${name}`);
            return true;

        } catch (err) {
            notifyLuaCrash(err.message || String(err), context);
            return false;
        }
    }

    // =========================================================================
    // Behavior Execution
    // =========================================================================

    function executeBehaviorUpdates(dt, entityData) {
        const emptyResult = { entities: {}, spawns: [], sounds: [], scheduled: [], score: 0 };

        // If crashed, return empty - game should have already stopped
        if (luaCrashed) {
            return emptyResult;
        }

        if (!luaReady) {
            return emptyResult;
        }

        // Update entity storage
        updateEntities(entityData);

        // Reset changes
        resetStateChanges();

        // Validate dt
        if (!Number.isFinite(dt) || dt < 0) {
            dt = 0.016;
        }

        let behaviorsRun = 0;

        // For each entity, call its behaviors
        for (const [entityId, entity] of Object.entries(entityData)) {
            // Check if we crashed during execution
            if (luaCrashed) break;

            if (!entity.alive || !entity.behaviors) continue;

            for (const behaviorName of entity.behaviors) {
                if (luaCrashed) break;

                const globalName = subroutines.behavior[behaviorName];
                if (!globalName) continue;

                // Call behavior.on_update(entityId, dt)
                // NO pcall wrapper - we want errors to propagate and crash the engine
                const callCode = `
                    local b = ${globalName}
                    if b and b.on_update then
                        b.on_update("${entityId}", ${dt})
                    end
                `;
                doString(callCode, `behavior_${behaviorName}_update`);
                behaviorsRun++;
            }
        }

        // Log occasionally (only if not crashed)
        if (!luaCrashed && (gameState.elapsedTime < 1.0 || Math.floor(gameState.elapsedTime) % 5 === 0)) {
            const changedCount = Object.keys(stateChanges.entities).length;
            console.log(`[FENGARI] Frame: ${Object.keys(entityData).length} entities, ${behaviorsRun} behaviors, ${changedCount} changed`);
        }

        return { ...stateChanges };
    }

    // =========================================================================
    // Collision Action Execution
    // =========================================================================

    function executeCollisionAction(actionName, entityA, entityB, modifier) {
        const emptyResult = { entities: {}, spawns: [], sounds: [], scheduled: [], score: 0 };

        if (!luaReady) return emptyResult;

        const globalName = subroutines.collision_action[actionName];
        if (!globalName) {
            console.warn(`[FENGARI] Collision action not found: ${actionName}`);
            return emptyResult;
        }

        // Update entity storage with collision entities
        entities[entityA.id] = entityA;
        entities[entityB.id] = entityB;

        // Reset changes
        resetStateChanges();

        // Pass modifier as global if provided
        if (modifier) {
            setGlobal('_collision_modifier', modifier);
        } else {
            doString('_collision_modifier = nil', 'modifier_nil');
        }

        // Call action.execute(a_id, b_id, modifier)
        const callCode = `
            local a = ${globalName}
            if a and a.execute then
                local ok, err = pcall(a.execute, "${entityA.id}", "${entityB.id}", _collision_modifier)
                if not ok then
                    ams.log("Error in ${actionName}.execute: " .. tostring(err))
                end
            end
        `;
        doString(callCode, `collision_${actionName}`);

        return { ...stateChanges };
    }

    // =========================================================================
    // Message Handling (from Python)
    // =========================================================================

    function handlePythonMessage(event) {
        let msg;
        try {
            if (typeof event.data === 'string') {
                msg = JSON.parse(event.data);
            } else {
                msg = event.data;
            }
        } catch {
            return;
        }

        if (msg.source !== 'lua_engine') return;

        const { type, data } = msg;

        switch (type) {
            case 'lua_init':
                gameState.screenWidth = data.screen_width || 800;
                gameState.screenHeight = data.screen_height || 600;
                initFengari();
                break;

            case 'lua_load_subroutine':
                loadSubroutine(data.sub_type, data.name, data.code);
                break;

            case 'lua_update':
                gameState.elapsedTime = data.elapsed_time || 0;
                gameState.score = data.score || 0;

                if (gameState.elapsedTime < 0.5) {
                    console.log('[FENGARI] lua_update received, entities:', Object.keys(data.entities || {}).length);
                }

                const results = executeBehaviorUpdates(data.dt, data.entities);

                window.luaResponses.push(JSON.stringify({
                    type: 'lua_update_result',
                    data: results
                }));
                break;

            case 'lua_collision':
                const collisionResult = executeCollisionAction(
                    data.action,
                    data.entity_a,
                    data.entity_b,
                    data.modifier
                );

                window.luaResponses.push(JSON.stringify({
                    type: 'lua_collision_result',
                    data: collisionResult
                }));
                break;

            case 'lua_set_global':
                if (luaReady) {
                    setGlobal(data.name, data.value);
                }
                break;
        }
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    // Set up logging and error handlers
    if (typeof window !== 'undefined') {
        getLogConfig(); // Sets logStreamEnabled
        setupGlobalErrorHandlers(); // Always capture errors
        if (logStreamEnabled) {
            setupConsoleInterception();
            initLogStream();
        }

        // Expose streamLog globally for early error handlers (injected into index.html)
        window.AMS_streamLog = streamLog;

        // Process any early errors captured before fengari_bridge loaded
        if (window.AMS_EARLY_ERRORS && window.AMS_EARLY_ERRORS.length > 0) {
            console.log(`[FENGARI] Processing ${window.AMS_EARLY_ERRORS.length} early errors`);
            window.AMS_EARLY_ERRORS.forEach(function(err) {
                streamLog('ERROR', 'early_' + err.type, JSON.stringify(err));
            });
        }
    }

    // Listen for messages from Python
    window.addEventListener('message', handlePythonMessage);

    // Expose bridge API for direct access
    window.fengariBridge = {
        init: initFengari,
        loadSubroutine,
        executeBehaviorUpdates,
        executeCollisionAction,
        isReady: () => luaReady,
        isCrashed: () => luaCrashed,
        getCrashError: () => luaCrashError,
        getEntities: () => entities,
        getStateChanges: () => stateChanges
    };

    // Also expose as wasmoonBridge for compatibility with existing Python code
    window.wasmoonBridge = window.fengariBridge;

    console.log(`[FENGARI Bridge] Loaded ${VERSION}`);

    // Signal ready
    window.fengariBridgeReady = true;
    window.wasmoonBridgeReady = true;  // Compatibility

})();
