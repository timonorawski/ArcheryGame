# Game Engine Extraction Refactor

**Status: COMPLETE** (commit 61ea1b7)

## Goal

Restructure the codebase to:
1. Move game engine from `games/common/` to `ams/games/`
2. Extract generalizable Lua engine from `ams/behaviors/` to `ams/lua/`
3. Keep Lua assets (behaviors, collision_actions, generators) as game_engine core assets
4. Split Entity into ABC (reusable) and GameEntity (game-specific)

## Final Structure

```
ams/
├── lua/                            # Core Lua sandbox (REUSABLE)
│   ├── __init__.py
│   ├── engine.py                   # LuaEngine (accepts api_class parameter)
│   ├── entity.py                   # Entity ABC (id, type, properties, behaviors)
│   └── api.py                      # LuaAPIBase (property access, math, logging)
│
├── games/                          # Game infrastructure (from games/common/)
│   ├── __init__.py
│   ├── base_game.py                # Base class for all games
│   ├── game_state.py               # GameState enum
│   ├── levels.py                   # Level loading system
│   ├── level_chooser.py            # Level selection UI
│   ├── pacing.py                   # Device pacing presets
│   ├── palette.py                  # Color palette management
│   ├── quiver.py                   # Ammo management
│   ├── input/                      # Input abstraction layer
│   │   ├── __init__.py
│   │   ├── input_event.py
│   │   ├── input_manager.py
│   │   └── sources/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       └── mouse.py
│   └── game_engine/                # YAML-driven game framework
│       ├── __init__.py
│       ├── engine.py               # GameEngine (uses LuaEngine + GameLuaAPI)
│       ├── entity.py               # GameEntity(Entity) - transform, physics, visuals
│       ├── api.py                  # GameLuaAPI(LuaAPIBase) - game-specific methods
│       └── lua/                    # Lua assets
│           ├── __init__.py
│           ├── behaviors/          # .lua entity behaviors
│           ├── collision_actions/  # .lua collision handlers
│           └── generators/         # .lua property generators
│
├── input_actions/                  # Keep here (game engine uses via ContentFS)
│   └── *.lua
│
├── content_fs.py                   # Keep (already in place)
└── ...
```

## Actual Path Mapping

| Original Path | Final Path | Notes |
|--------------|----------|-------|
| `games/common/game_engine.py` | `ams/games/game_engine/engine.py` | GameEngine class |
| `games/common/base_game.py` | `ams/games/base_game.py` | |
| `games/common/game_state.py` | `ams/games/game_state.py` | |
| `games/common/levels.py` | `ams/games/levels.py` | |
| `games/common/level_chooser.py` | `ams/games/level_chooser.py` | |
| `games/common/pacing.py` | `ams/games/pacing.py` | |
| `games/common/palette.py` | `ams/games/palette.py` | |
| `games/common/quiver.py` | `ams/games/quiver.py` | |
| `games/common/input/` | `ams/games/input/` | |
| `ams/behaviors/engine.py` | `ams/lua/engine.py` | Renamed BehaviorEngine → LuaEngine |
| `ams/behaviors/entity.py` | `ams/lua/entity.py` | Became Entity ABC |
| (new) | `ams/games/game_engine/entity.py` | GameEntity(Entity) concrete class |
| `ams/behaviors/api.py` | `ams/lua/api.py` | Became LuaAPIBase (minimal) |
| (new) | `ams/games/game_engine/api.py` | GameLuaAPI(LuaAPIBase) game methods |
| `ams/behaviors/lua/` | `ams/games/game_engine/lua/behaviors/` | |
| `ams/behaviors/collision_actions/` | `ams/games/game_engine/lua/collision_actions/` | |
| `ams/behaviors/generators/` | `ams/games/game_engine/lua/generators/` | |

## Import Updates (Completed)

### Key Import Changes

| Old Import | New Import |
|------------|------------|
| `from games.common import GameState` | `from ams.games import GameState` |
| `from games.common import BaseGame` | `from ams.games import BaseGame` |
| `from games.common import GameEngine` | `from ams.games.game_engine import GameEngine` |
| `from games.common.input import InputEvent, InputManager` | `from ams.games.input import InputEvent, InputManager` |
| `from ams.behaviors.engine import BehaviorEngine` | `from ams.lua.engine import LuaEngine` |
| `from ams.behaviors.api import _to_lua_value` | `from ams.lua.api import _to_lua_value` |

### New Classes

| Class | Location | Purpose |
|-------|----------|---------|
| `Entity` | `ams.lua.entity` | ABC - minimal contract (id, type, properties, behaviors) |
| `GameEntity` | `ams.games.game_engine.entity` | Concrete entity with transform, physics, visuals |
| `LuaAPIBase` | `ams.lua.api` | Base API (property access, math, logging) |
| `GameLuaAPI` | `ams.games.game_engine.api` | Game-specific API (position, velocity, spawn, etc.) |
| `LuaEngine` | `ams.lua.engine` | Core Lua sandbox, accepts `api_class` parameter |

### Backward Compatibility

`games/common/__init__.py` re-exports from `ams.games` for legacy imports.

### Files Requiring Import Updates (~25 files)

**Game mode files (13):**
- `games/BalloonPop/game_mode.py`
- `games/BrickBreaker/game_mode.py`
- `games/Containment/game_mode.py`
- `games/DuckHunt/game_mode.py`
- `games/FruitSlice/game_mode.py`
- `games/Gradient/game_mode.py`
- `games/Grouping/game_mode.py`
- `games/GrowingTargets/game_mode.py`
- `games/LoveOMeter/game_mode.py`
- `games/ManyTargets/game_mode.py`
- `games/SweetPhysics/game_mode.py`
- `games/BrickBreaker/main.py`
- `games/Containment/main.py`

**Registry and integration:**
- `games/registry.py`
- `ams/web_controller/ams_integration.py`

**Models:**
- `models/duckhunt/__init__.py`
- `models/duckhunt/enums.py`

**Tests:**
- `tests/test_lua_sandbox.py`

**Game-local input wrappers (can be removed or updated):**
- `games/ManyTargets/input/` (5 files)
- `games/Grouping/input/` (5 files)
- `games/GrowingTargets/input/` (5 files)

## ContentFS Path Updates

The behavior engine loads Lua files via ContentFS. Update paths:

| Old ContentFS Path | New ContentFS Path |
|--------------------|-------------------|
| `ams/behaviors/lua/` | `ams/games/game_engine/lua/behaviors/` |
| `ams/behaviors/collision_actions/` | `ams/games/game_engine/lua/collision_actions/` |
| `ams/behaviors/generators/` | `ams/games/game_engine/lua/generators/` |
| `ams/input_actions/` | `ams/input_actions/` (no change) |

## Implementation Steps

### Phase 1: Create New Directory Structure
```bash
mkdir -p ams/games/input/sources
mkdir -p ams/games/game_engine/lua/behaviors
mkdir -p ams/games/game_engine/lua/collision_actions
mkdir -p ams/games/game_engine/lua/generators
mkdir -p ams/lua
```

### Phase 2: Move Supporting Files (games/common → ams/games)
```bash
# Core game abstractions
mv games/common/base_game.py ams/games/
mv games/common/game_state.py ams/games/
mv games/common/levels.py ams/games/
mv games/common/level_chooser.py ams/games/
mv games/common/pacing.py ams/games/
mv games/common/palette.py ams/games/
mv games/common/quiver.py ams/games/

# Input system
mv games/common/input/input_event.py ams/games/input/
mv games/common/input/input_manager.py ams/games/input/
mv games/common/input/sources/base.py ams/games/input/sources/
mv games/common/input/sources/mouse.py ams/games/input/sources/
```

### Phase 3: Move Game Engine
```bash
# Main GameEngine class
mv games/common/game_engine.py ams/games/game_engine/engine.py
```

### Phase 4: Move Lua Engine (ams/behaviors/engine.py → ams/lua/)
```bash
# Core Lua engine (rename BehaviorEngine → LuaEngine)
mv ams/behaviors/engine.py ams/lua/engine.py
# Then rename class BehaviorEngine to LuaEngine in the file
```

### Phase 5: Move Game-Engine Lua Components
```bash
# Entity and API (game-engine specific)
mv ams/behaviors/entity.py ams/games/game_engine/lua/entity.py
mv ams/behaviors/api.py ams/games/game_engine/lua/api.py

# Lua assets (game-engine core behaviors)
mv ams/behaviors/lua/* ams/games/game_engine/lua/behaviors/
mv ams/behaviors/collision_actions/* ams/games/game_engine/lua/collision_actions/
mv ams/behaviors/generators/* ams/games/game_engine/lua/generators/
```

Note: After this split, `ams.lua.LuaEngine` is the reusable sandboxed Lua runtime.
The game engine's `GameEngine` class uses `LuaEngine` and adds Entity/API/behavior management.

### Phase 6: Create __init__.py Files
1. `ams/lua/__init__.py` - export LuaEngine
2. `ams/games/__init__.py` - export GameState, BaseGame, etc.
3. `ams/games/input/__init__.py` - export InputEvent, InputManager
4. `ams/games/input/sources/__init__.py` - export InputSource, MouseInputSource
5. `ams/games/game_engine/__init__.py` - export GameEngine, GameEngineSkin
6. `ams/games/game_engine/lua/__init__.py` - export Entity, LuaAPI

### Phase 7: Update Internal Imports
1. Fix relative imports within `ams/games/` (base_game, levels, etc.)
2. Fix imports within `ams/games/game_engine/lua/` (engine, entity, api)
3. Update `ams/games/game_engine/engine.py` to import from `..lua`

### Phase 8: Update External Imports
1. Update all game_mode.py files (13 files)
2. Update games/registry.py
3. Update ams/web_controller/ams_integration.py
4. Update models/duckhunt/
5. Update tests/test_lua_sandbox.py

### Phase 9: Update ContentFS Paths
Update default paths in `ams/lua/engine.py` (LuaEngine):
- `ams/behaviors/lua/` → `ams/games/game_engine/lua/behaviors/`
- `ams/behaviors/collision_actions/` → `ams/games/game_engine/lua/collision_actions/`
- `ams/behaviors/generators/` → `ams/games/game_engine/lua/generators/`

### Phase 10: Cleanup
1. Remove empty `ams/behaviors/` directory
2. Remove empty `games/common/` directory
3. Optionally remove game-local input wrappers (now redundant)
4. Update documentation (CLAUDE.md, architecture docs)

### Phase 11: Testing
```bash
pytest tests/test_lua_sandbox.py -v          # All 105 tests pass
python dev_game.py --list                    # List all games
python dev_game.py sweetphysicsng            # YAML-driven game
python dev_game.py duckhunt                  # Python game
```

## Files to Create

| File | Purpose |
|------|---------|
| `ams/lua/__init__.py` | Export LuaEngine |
| `ams/games/__init__.py` | Export GameState, BaseGame, pacing, palette, quiver, levels |
| `ams/games/input/__init__.py` | Export InputEvent, InputManager |
| `ams/games/input/sources/__init__.py` | Export InputSource, MouseInputSource |
| `ams/games/game_engine/__init__.py` | Export GameEngine, GameEngineSkin, etc. |
| `ams/games/game_engine/lua/__init__.py` | Export Entity, LuaAPI |

## Verification (PASSED)

All tests pass and games work:
```bash
pytest tests/test_lua_sandbox.py -v          # ✓ 105 passed
python dev_game.py --list                    # ✓ 17 games listed
python dev_game.py sweetphysicsng            # ✓ YAML-driven game works
python dev_game.py duckhunt                  # ✓ Python game works
```

## Implementation Notes

### Entity ABC Split

The original plan had Entity in `ams/games/game_engine/lua/`. During implementation,
we recognized that Entity is a generic mapper for Lua behaviors, not game-specific.

Final design:
- `Entity` ABC in `ams/lua/` - defines minimal contract for behavior attachment
- `GameEntity(Entity)` in `ams/games/game_engine/` - adds game-specific fields

### API Split

Similarly, the Lua API was split:
- `LuaAPIBase` in `ams/lua/api.py` - property access, math helpers, logging
- `GameLuaAPI(LuaAPIBase)` in `ams/games/game_engine/api.py` - game operations

`LuaEngine` accepts an `api_class` parameter (defaults to `LuaAPIBase`).
`GameEngine` passes `GameLuaAPI` for full game functionality.

### Circular Import Resolution

Avoided circular imports by:
1. Lazy importing `GameEntity` in `LuaEngine.create_entity()`
2. Direct module imports instead of through `__init__.py` where needed
