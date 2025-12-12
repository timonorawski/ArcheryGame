#!/usr/bin/env node
/**
 * WASMOON Sandbox Test - Node.js Version
 * Tests what globals are available in WASMOON's Lua environment
 */

import { LuaFactory } from 'wasmoon';

const PASS = '\x1b[32m✓\x1b[0m';
const FAIL = '\x1b[31m✗\x1b[0m';
const WARN = '\x1b[33m⚠\x1b[0m';
const INFO = '\x1b[34mℹ\x1b[0m';

function log(msg, status = 'info') {
    const prefix = status === 'pass' ? PASS : status === 'fail' ? FAIL : status === 'warn' ? WARN : INFO;
    console.log(`${prefix} ${msg}`);
}

async function main() {
    console.log('\n=== WASMOON SANDBOX TEST RIG (Node.js) ===\n');

    // Initialize WASMOON
    log('Initializing WASMOON...');
    let factory, luaEngine;
    try {
        factory = new LuaFactory();
        luaEngine = await factory.createEngine();
        log('WASMOON initialized successfully!', 'pass');
    } catch (err) {
        log(`Failed to initialize WASMOON: ${err.message}`, 'fail');
        process.exit(1);
    }

    // Helper to test a global
    async function testGlobal(name) {
        try {
            const code = `if ${name} ~= nil then return "EXISTS" else return "NIL" end`;
            const result = await luaEngine.doString(code);
            const status = result === 'EXISTS' ? 'pass' : 'warn';
            log(`  ${name}: ${result}`, status);
            return result === 'EXISTS';
        } catch (e) {
            log(`  ${name}: ERROR - ${e.message}`, 'fail');
            return false;
        }
    }

    // Test 1: Basic Globals
    console.log('\n=== TEST 1: BASIC GLOBALS ===');
    const basicGlobals = ['print', 'type', 'tostring', 'tonumber', 'pairs', 'ipairs', 'next', 'select', 'pcall', 'xpcall', 'error', 'assert'];
    for (const g of basicGlobals) {
        await testGlobal(g);
    }

    // Test 2: Table/Metatable Functions
    console.log('\n=== TEST 2: TABLE FUNCTIONS ===');
    const tableFuncs = ['table', 'setmetatable', 'getmetatable', 'rawget', 'rawset', 'rawequal', 'rawlen'];
    for (const g of tableFuncs) {
        await testGlobal(g);
    }

    // Test 3: Code Loading Functions
    console.log('\n=== TEST 3: CODE LOADING ===');
    const loadFuncs = ['load', 'loadfile', 'loadstring', 'dofile'];
    for (const g of loadFuncs) {
        await testGlobal(g);
    }

    // Test 4: Libraries
    console.log('\n=== TEST 4: STANDARD LIBRARIES ===');
    const libs = ['math', 'string', 'table', 'os', 'io', 'coroutine', 'debug', 'utf8', 'package'];
    for (const g of libs) {
        await testGlobal(g);
    }

    // Test 5: Special Globals
    console.log('\n=== TEST 5: SPECIAL GLOBALS ===');
    const specialGlobals = ['_G', '_ENV', '_VERSION'];
    for (const g of specialGlobals) {
        await testGlobal(g);
    }

    // Test 6: Global Persistence
    console.log('\n=== TEST 6: GLOBAL PERSISTENCE ===');
    log('Setting _test_var = 12345...');
    await luaEngine.doString('_test_var = 12345');
    log('Reading _test_var in new doString...');
    const persistResult = await luaEngine.doString('return _test_var');
    log(`Result: ${persistResult}`, persistResult === 12345 ? 'pass' : 'fail');

    // Test 7: Function _ENV Capture
    console.log('\n=== TEST 7: FUNCTION _ENV CAPTURE ===');
    log('Defining function that accesses global...');
    await luaEngine.doString(`
        _shared_value = 999
        function test_func()
            return _shared_value
        end
    `);
    log('Calling function from new doString...');
    try {
        const funcResult = await luaEngine.doString('return test_func()');
        log(`Result: ${funcResult}`, funcResult === 999 ? 'pass' : 'fail');
    } catch (e) {
        log(`Function call failed: ${e.message}`, 'fail');
    }

    // Test 8: Closure with Upvalue
    console.log('\n=== TEST 8: CLOSURE WITH UPVALUE ===');
    log('Defining closure with captured upvalue...');
    await luaEngine.doString(`
        local captured = 777
        function closure_test()
            return captured
        end
    `);
    log('Calling closure from new doString...');
    try {
        const closureResult = await luaEngine.doString('return closure_test()');
        log(`Result: ${closureResult}`, closureResult === 777 ? 'pass' : 'fail');
    } catch (e) {
        log(`Closure call failed: ${e.message}`, 'fail');
    }

    // Test 9: JS Function Injection via global.set
    console.log('\n=== TEST 9: JS FUNCTION INJECTION ===');
    log('Injecting JS function via global.set...');
    try {
        luaEngine.global.set('js_callback', (x) => {
            console.log(`  [JS] Callback called with: ${x}`);
            return x * 2;
        });
        log('Calling from Lua...');
        const jsResult = await luaEngine.doString('return js_callback(21)');
        log(`Result: ${jsResult}`, jsResult === 42 ? 'pass' : 'fail');
    } catch (e) {
        log(`JS function injection failed: ${e.message}`, 'fail');
    }

    // Test 10: global.set for Variables
    console.log('\n=== TEST 10: global.set FOR VARIABLES ===');
    log('Setting global via JS: luaEngine.global.set("js_var", 123)');
    luaEngine.global.set('js_var', 123);
    log('Reading via doString...');
    const jsVarResult = await luaEngine.doString('return js_var');
    log(`Result: ${jsVarResult}`, jsVarResult === 123 ? 'pass' : 'fail');

    // Test 11: What does _ENV actually look like?
    console.log('\n=== TEST 11: _ENV EXPLORATION ===');
    try {
        const envType = await luaEngine.doString('return type(_ENV)');
        log(`type(_ENV) = ${envType}`);

        if (envType === 'table') {
            const envKeys = await luaEngine.doString(`
                local keys = {}
                for k, v in pairs(_ENV) do
                    table.insert(keys, k)
                end
                return table.concat(keys, ", ")
            `);
            log(`_ENV keys: ${envKeys}`);
        }
    } catch (e) {
        log(`_ENV exploration failed: ${e.message}`, 'fail');
    }

    // Test 12: What does _G look like?
    console.log('\n=== TEST 12: _G EXPLORATION ===');
    try {
        const gType = await luaEngine.doString('return type(_G)');
        log(`type(_G) = ${gType}`);

        if (gType === 'table') {
            const gKeys = await luaEngine.doString(`
                local keys = {}
                for k, v in pairs(_G) do
                    table.insert(keys, k)
                end
                return table.concat(keys, ", ")
            `);
            log(`_G keys: ${gKeys}`);
        }
    } catch (e) {
        log(`_G exploration failed: ${e.message}`, 'fail');
    }

    // Test 13: Can we create our own environment?
    console.log('\n=== TEST 13: CUSTOM ENVIRONMENT VIA load() ===');
    try {
        const loadExists = await luaEngine.doString('return load ~= nil');
        if (loadExists) {
            log('load() exists, testing custom environment...');
            const loadResult = await luaEngine.doString(`
                local env = { x = 42 }
                local chunk = load("return x", "test", "t", env)
                if chunk then
                    return chunk()
                else
                    return "LOAD_FAILED"
                end
            `);
            log(`Custom env result: ${loadResult}`, loadResult === 42 ? 'pass' : 'fail');
        } else {
            log('load() does not exist', 'warn');
        }
    } catch (e) {
        log(`Custom environment test failed: ${e.message}`, 'fail');
    }

    // Test 14: setfenv (Lua 5.1 style)
    console.log('\n=== TEST 14: setfenv (Lua 5.1) ===');
    try {
        const setfenvExists = await luaEngine.doString('return setfenv ~= nil');
        log(`setfenv exists: ${setfenvExists}`);

        const getfenvExists = await luaEngine.doString('return getfenv ~= nil');
        log(`getfenv exists: ${getfenvExists}`);
    } catch (e) {
        log(`setfenv/getfenv test failed: ${e.message}`, 'fail');
    }

    console.log('\n=== ALL TESTS COMPLETE ===\n');

    // Close the engine
    luaEngine.global.close();
}

main().catch(console.error);
