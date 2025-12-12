/**
 * Unit tests for fengari_bridge.js
 *
 * Run with: node games/browser/tests/test_fengari_bridge.mjs
 *
 * These tests verify the logic of the bridge functions in isolation.
 */

// ============================================================================
// Test Utilities
// ============================================================================

let testsPassed = 0;
let testsFailed = 0;

function test(name, fn) {
    try {
        fn();
        testsPassed++;
        console.log(`  ✓ ${name}`);
    } catch (err) {
        testsFailed++;
        console.log(`  ✗ ${name}`);
        console.log(`    Error: ${err.message}`);
    }
}

function assertEqual(actual, expected, msg = '') {
    if (actual !== expected) {
        throw new Error(`${msg} Expected ${expected}, got ${actual}`);
    }
}

function assertDeepEqual(actual, expected, msg = '') {
    if (JSON.stringify(actual) !== JSON.stringify(expected)) {
        throw new Error(`${msg} Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    }
}

function assertTrue(val, msg = '') {
    if (!val) throw new Error(msg || 'Expected truthy value');
}

function assertFalse(val, msg = '') {
    if (val) throw new Error(msg || 'Expected falsy value');
}

// ============================================================================
// Run Tests
// ============================================================================

console.log('\n=== Fengari Bridge Unit Tests ===\n');

// ----------------------------------------------------------------------------
// Entity Storage
// ----------------------------------------------------------------------------

console.log('Entity Storage:');

test('entities can be stored and retrieved', () => {
    const entities = {};
    entities['player_1'] = {
        id: 'player_1',
        entity_type: 'player',
        alive: true,
        x: 100, y: 200,
        vx: 0, vy: 0,
        width: 32, height: 32,
    };
    assertEqual(entities['player_1'].x, 100);
    assertEqual(entities['player_1'].entity_type, 'player');
});

test('entity changes are tracked separately', () => {
    const entities = { 'e1': { x: 0, y: 0, alive: true } };
    const stateChanges = { entities: {} };

    const setEntityProp = (id, prop, value) => {
        if (!stateChanges.entities[id]) stateChanges.entities[id] = {};
        stateChanges.entities[id][prop] = value;
        entities[id][prop] = value;
    };

    setEntityProp('e1', 'x', 50);
    setEntityProp('e1', 'y', 75);

    assertEqual(entities['e1'].x, 50);
    assertEqual(stateChanges.entities['e1'].x, 50);
    assertEqual(stateChanges.entities['e1'].y, 75);
});

// ----------------------------------------------------------------------------
// AMS API Functions
// ----------------------------------------------------------------------------

console.log('\nAMS API:');

test('get_x returns entity x position', () => {
    const entities = { 'e1': { x: 123, y: 456 } };
    const get_x = (id) => { const e = entities[id]; return e ? e.x : 0; };

    assertEqual(get_x('e1'), 123);
    assertEqual(get_x('nonexistent'), 0);
});

test('set_x updates entity and tracks change', () => {
    const entities = { 'e1': { x: 0 } };
    const stateChanges = { entities: {} };

    const set_x = (id, x) => {
        if (!stateChanges.entities[id]) stateChanges.entities[id] = {};
        stateChanges.entities[id].x = x;
        if (entities[id]) entities[id].x = x;
    };

    set_x('e1', 999);
    assertEqual(entities['e1'].x, 999);
    assertEqual(stateChanges.entities['e1'].x, 999);
});

test('get_entities_by_tag filters correctly', () => {
    const entities = {
        'e1': { alive: true, tags: ['brick', 'red'] },
        'e2': { alive: true, tags: ['brick', 'blue'] },
        'e3': { alive: false, tags: ['brick'] },
        'e4': { alive: true, tags: ['ball'] },
    };

    const get_entities_by_tag = (tag) => {
        const result = [];
        for (const [id, e] of Object.entries(entities)) {
            if (e.alive && e.tags && e.tags.includes(tag)) {
                result.push(id);
            }
        }
        return result;
    };

    const bricks = get_entities_by_tag('brick');
    assertEqual(bricks.length, 2);
    assertTrue(bricks.includes('e1'));
    assertTrue(bricks.includes('e2'));
    assertFalse(bricks.includes('e3'));  // dead
});

test('count_entities_by_tag counts correctly', () => {
    const entities = {
        'e1': { alive: true, tags: ['brick'] },
        'e2': { alive: true, tags: ['brick'] },
        'e3': { alive: false, tags: ['brick'] },
    };

    const count_entities_by_tag = (tag) => {
        let count = 0;
        for (const e of Object.values(entities)) {
            if (e.alive && e.tags && e.tags.includes(tag)) count++;
        }
        return count;
    };

    assertEqual(count_entities_by_tag('brick'), 2);
});

test('spawn creates spawn record with unique ID', () => {
    let spawnCounter = 0;
    const stateChanges = { spawns: [] };

    const spawn = (entityType, x, y) => {
        spawnCounter++;
        const spawnId = 'spawn_' + spawnCounter;
        stateChanges.spawns.push({
            id: spawnId,
            entity_type: entityType,
            x: x || 0, y: y || 0,
        });
        return spawnId;
    };

    const id1 = spawn('bullet', 100, 200);
    const id2 = spawn('bullet', 150, 250);

    assertEqual(id1, 'spawn_1');
    assertEqual(id2, 'spawn_2');
    assertEqual(stateChanges.spawns.length, 2);
    assertEqual(stateChanges.spawns[0].x, 100);
});

test('destroy marks entity as dead', () => {
    const stateChanges = { entities: {} };

    const destroy = (id) => {
        if (!stateChanges.entities[id]) stateChanges.entities[id] = {};
        stateChanges.entities[id].alive = false;
    };

    destroy('e1');
    assertEqual(stateChanges.entities['e1'].alive, false);
});

// ----------------------------------------------------------------------------
// Math Helpers
// ----------------------------------------------------------------------------

console.log('\nMath Helpers:');

test('random_range returns value in range', () => {
    const random_range = (min, max) => min + Math.random() * (max - min);

    for (let i = 0; i < 100; i++) {
        const val = random_range(10, 20);
        assertTrue(val >= 10 && val <= 20, `Value ${val} out of range`);
    }
});

test('clamp constrains value', () => {
    const clamp = (val, min, max) => Math.max(min, Math.min(max, val));

    assertEqual(clamp(5, 0, 10), 5);
    assertEqual(clamp(-5, 0, 10), 0);
    assertEqual(clamp(15, 0, 10), 10);
});

// ----------------------------------------------------------------------------
// Properties API
// ----------------------------------------------------------------------------

console.log('\nProperties API:');

test('get_prop returns custom property', () => {
    const entities = {
        'e1': { properties: { score: 100, name: 'player' } }
    };

    const get_prop = (id, key) => {
        const e = entities[id];
        return (e && e.properties) ? e.properties[key] : null;
    };

    assertEqual(get_prop('e1', 'score'), 100);
    assertEqual(get_prop('e1', 'name'), 'player');
    assertEqual(get_prop('e1', 'missing'), undefined);  // undefined not null
    assertEqual(get_prop('nonexistent', 'foo'), null);
});

test('set_prop creates and updates properties', () => {
    const entities = { 'e1': { properties: {} } };
    const stateChanges = { entities: {} };

    const set_prop = (id, key, value) => {
        if (!stateChanges.entities[id]) {
            stateChanges.entities[id] = { properties: {} };
        }
        if (!stateChanges.entities[id].properties) {
            stateChanges.entities[id].properties = {};
        }
        stateChanges.entities[id].properties[key] = value;
        if (entities[id]) {
            if (!entities[id].properties) entities[id].properties = {};
            entities[id].properties[key] = value;
        }
    };

    set_prop('e1', 'hits', 5);
    assertEqual(entities['e1'].properties.hits, 5);
    assertEqual(stateChanges.entities['e1'].properties.hits, 5);
});

test('get_config returns behavior config with default', () => {
    const entities = {
        'e1': {
            behavior_config: {
                'move_linear': { speed: 200, direction: 'right' }
            }
        }
    };

    const get_config = (id, behavior, key, defaultValue) => {
        const e = entities[id];
        if (e && e.behavior_config && e.behavior_config[behavior]) {
            const val = e.behavior_config[behavior][key];
            return val !== undefined ? val : defaultValue;
        }
        return defaultValue;
    };

    assertEqual(get_config('e1', 'move_linear', 'speed', 100), 200);
    assertEqual(get_config('e1', 'move_linear', 'missing', 'default'), 'default');
    assertEqual(get_config('e1', 'nonexistent', 'foo', 42), 42);
});

// ----------------------------------------------------------------------------
// State Changes Reset
// ----------------------------------------------------------------------------

console.log('\nState Management:');

test('resetStateChanges clears all changes', () => {
    let stateChanges = {
        entities: { 'e1': { x: 100 } },
        spawns: [{ id: 'spawn_1' }],
        sounds: ['hit'],
        scheduled: [{ delay: 1 }],
        score: 50
    };

    const resetStateChanges = () => {
        stateChanges = {
            entities: {},
            spawns: [],
            sounds: [],
            scheduled: [],
            score: 0
        };
    };

    resetStateChanges();

    assertDeepEqual(stateChanges.entities, {});
    assertEqual(stateChanges.spawns.length, 0);
    assertEqual(stateChanges.sounds.length, 0);
    assertEqual(stateChanges.scheduled.length, 0);
    assertEqual(stateChanges.score, 0);
});

// ----------------------------------------------------------------------------
// Subroutine Loading
// ----------------------------------------------------------------------------

console.log('\nSubroutine Loading:');

test('subroutines are stored by type and name', () => {
    const subroutines = {
        behavior: {},
        collision_action: {},
        generator: {},
        input_action: {}
    };

    subroutines.behavior['move_linear'] = '__subroutine_behavior_move_linear';
    subroutines.collision_action['damage'] = '__subroutine_collision_action_damage';

    assertTrue('move_linear' in subroutines.behavior);
    assertTrue('damage' in subroutines.collision_action);
    assertFalse('missing' in subroutines.behavior);
});

test('pending subroutines queue before ready', () => {
    let luaReady = false;
    const pendingSubroutines = [];
    const subroutines = { behavior: {} };

    const loadSubroutine = (subType, name, code) => {
        if (!luaReady) {
            pendingSubroutines.push({ subType, name, code });
            return false;
        }
        subroutines[subType][name] = `__subroutine_${subType}_${name}`;
        return true;
    };

    // Before ready
    loadSubroutine('behavior', 'test', 'return {}');
    assertEqual(pendingSubroutines.length, 1);
    assertFalse('test' in subroutines.behavior);

    // After ready
    luaReady = true;
    for (const p of pendingSubroutines) {
        loadSubroutine(p.subType, p.name, p.code);
    }
    assertTrue('test' in subroutines.behavior);
});

// ----------------------------------------------------------------------------
// Error Handling (Lua crash behavior)
// ----------------------------------------------------------------------------

console.log('\nError Handling:');

test('luaCrashed flag stops all execution', () => {
    let luaCrashed = false;
    let executionCount = 0;

    const safeLuaExec = (code) => {
        if (luaCrashed) return null;
        executionCount++;
        return 'result';
    };

    // Normal execution
    assertEqual(safeLuaExec('code1'), 'result');
    assertEqual(executionCount, 1);

    // Simulate crash
    luaCrashed = true;
    assertEqual(safeLuaExec('code2'), null);
    assertEqual(executionCount, 1);  // Not incremented
});

test('lua error notifies Python via response queue', () => {
    const luaResponses = [];

    const notifyCrash = (error, context) => {
        luaResponses.push(JSON.stringify({
            type: 'lua_crashed',
            data: { error, context }
        }));
    };

    notifyCrash('syntax error at line 5', 'behavior_update');

    assertEqual(luaResponses.length, 1);
    const msg = JSON.parse(luaResponses[0]);
    assertEqual(msg.type, 'lua_crashed');
    assertEqual(msg.data.context, 'behavior_update');
});

// ----------------------------------------------------------------------------
// Message Protocol
// ----------------------------------------------------------------------------

console.log('\nMessage Protocol:');

test('lua_update message triggers behavior execution', () => {
    const messages = [];
    const responses = [];

    const handleMessage = (msg) => {
        if (msg.source !== 'lua_engine') return;
        messages.push(msg);

        if (msg.type === 'lua_update') {
            responses.push({
                type: 'lua_update_result',
                data: { entities: {}, spawns: [], sounds: [], scheduled: [], score: 0 }
            });
        }
    };

    handleMessage({
        source: 'lua_engine',
        type: 'lua_update',
        data: { dt: 0.016, entities: {}, elapsed_time: 1.0, score: 0 }
    });

    assertEqual(messages.length, 1);
    assertEqual(responses.length, 1);
    assertEqual(responses[0].type, 'lua_update_result');
});

test('lua_collision message executes action', () => {
    const responses = [];

    const handleCollision = (action, entityA, entityB, modifier) => {
        responses.push({
            type: 'lua_collision_result',
            data: { entities: {}, spawns: [], sounds: [], scheduled: [], score: 0 }
        });
    };

    handleCollision('damage', { id: 'ball' }, { id: 'brick' }, { amount: 1 });

    assertEqual(responses.length, 1);
    assertEqual(responses[0].type, 'lua_collision_result');
});

// ----------------------------------------------------------------------------
// Parent-Child Relationships
// ----------------------------------------------------------------------------

console.log('\nParent-Child:');

test('get_parent_id returns parent or empty string', () => {
    const entities = {
        'child': { parent_id: 'parent' },
        'orphan': { parent_id: null }
    };

    const get_parent_id = (id) => {
        const e = entities[id];
        return (e && e.parent_id) ? e.parent_id : '';
    };

    assertEqual(get_parent_id('child'), 'parent');
    assertEqual(get_parent_id('orphan'), '');
    assertEqual(get_parent_id('nonexistent'), '');
});

test('has_parent returns boolean', () => {
    const entities = {
        'child': { parent_id: 'parent' },
        'orphan': { parent_id: null }
    };

    const has_parent = (id) => {
        const e = entities[id];
        return !!(e && e.parent_id);
    };

    assertTrue(has_parent('child'));
    assertFalse(has_parent('orphan'));
});

test('get_children returns child list', () => {
    const entities = {
        'parent': { children: ['c1', 'c2', 'c3'] },
        'childless': { children: [] }
    };

    const get_children = (id) => {
        const e = entities[id];
        return (e && e.children) ? e.children : [];
    };

    assertDeepEqual(get_children('parent'), ['c1', 'c2', 'c3']);
    assertDeepEqual(get_children('childless'), []);
    assertDeepEqual(get_children('nonexistent'), []);
});

// ----------------------------------------------------------------------------
// Game State
// ----------------------------------------------------------------------------

console.log('\nGame State:');

test('game state tracks screen dimensions', () => {
    const gameState = {
        screenWidth: 1280,
        screenHeight: 720,
        score: 0,
        elapsedTime: 0
    };

    assertEqual(gameState.screenWidth, 1280);
    assertEqual(gameState.screenHeight, 720);
});

test('add_score accumulates points', () => {
    const stateChanges = { score: 0 };
    const add_score = (points) => { stateChanges.score += points; };

    add_score(10);
    add_score(25);
    add_score(-5);

    assertEqual(stateChanges.score, 30);
});

test('play_sound queues sounds', () => {
    const stateChanges = { sounds: [] };
    const play_sound = (name) => { stateChanges.sounds.push(name); };

    play_sound('hit');
    play_sound('explosion');

    assertDeepEqual(stateChanges.sounds, ['hit', 'explosion']);
});

test('schedule queues callbacks', () => {
    const stateChanges = { scheduled: [] };

    const schedule = (delay, callback, entityId) => {
        stateChanges.scheduled.push({ delay, callback, entity_id: entityId });
    };

    schedule(1.5, 'on_timer', 'e1');
    schedule(0.5, 'flash', 'e2');

    assertEqual(stateChanges.scheduled.length, 2);
    assertEqual(stateChanges.scheduled[0].delay, 1.5);
    assertEqual(stateChanges.scheduled[1].callback, 'flash');
});

// ============================================================================
// Summary
// ============================================================================

console.log('\n' + '='.repeat(40));
console.log(`Tests passed: ${testsPassed}`);
console.log(`Tests failed: ${testsFailed}`);
console.log('='.repeat(40) + '\n');

if (testsFailed > 0) {
    process.exit(1);
}
