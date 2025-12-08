# Technical Debt Summary

Last updated: December 2024

This document tracks known technical debt and improvement opportunities in the ArcheryGame codebase. Items are prioritized by impact and effort.

## High Priority (Fix Soon)

### ~~1. Duplicate Models Location~~ ✓ FIXED
**Issue**: `models.py` (root) duplicates definitions in `models/` package.
**Fix**: Deleted root `models.py`. All imports now use `models/` package.

### 2. DuckHunt Not Using BaseGame
**Issue**: DuckHunt has its own `GameMode` ABC (`games/DuckHunt/game/game_mode.py:16`) instead of inheriting from `BaseGame`.
**Impact**: Registry special-casing, inconsistent interface, harder to write game-agnostic code.
**Fix**: Either migrate DuckHunt to BaseGame or document architectural decision.

### 3. Hardcoded Path in detection_backend.py
**Issue**: Line 20 references `'Games'` instead of `'games'`.
```python
sys.path.insert(0, os.path.join(..., 'Games', 'DuckHunt'))  # Wrong
```
**Impact**: Case-sensitive systems will fail to find DuckHunt.
**Fix**: Change to lowercase `'games'`.

### 4. Missing Test Coverage
**Issue**: Only DuckHunt has tests (12 files). No tests for:
- AMS core (`ams/session.py`, detection backends)
- Calibration (`calibration/`)
- Game registry (`games/registry.py`)
- Other 7 games

**Impact**: Regressions can slip through unnoticed.
**Fix**: Add test suite for critical paths.

### 5. Migration Artifact Files
**Issue**: Leftover test files from BaseGame migration:
- `test_balloonpop_migration.py`
- `test_fruitslice_migration.py`
- `test_manytargets_migration.py`
- `quick_test.py`

**Fix**: Delete these files or integrate into proper test suite.

---

## Medium Priority (Plan Next)

### 6. Print Statements Instead of Logging
**Files affected**: 12+ files in `ams/` and `calibration/`
**Impact**: No log level control, hard to debug in production.
**Fix**: Replace `print()` with `logging` module.
**Status**: Partially done - loggers added to key modules (session, calibration, laser, object).
  - Remaining: Interactive calibration prompts still use print (intentional for user feedback)
  - See `docs/guides/AMS_DEVELOPER_GUIDE.md` for logging conventions

### 7. Bare Exception Handlers
**Files**: `ams/object_detection_backend.py` (lines 357, 437)
**Issue**: `except Exception:` hides specific errors.
**Fix**: Catch specific exceptions, add error logging.

### 8. Configuration Sprawl
**Issue**: 8 game config files + AMS config, each with redundant settings.
**Impact**: Inconsistencies between games, hard to change global settings.
**Fix**: Consider centralized config with game-specific overrides.

### 9. TODO Comments
| File | Line | Issue |
|------|------|-------|
| `ams/calibration.py` | 252 | CV backend contrast computation placeholder |
| `ams/calibration.py` | 279 | CV backend quality estimation placeholder |
| `games/DuckHunt/game/feedback.py` | 261 | Missing dedicated spawn sound |
| `games/DuckHunt/game/modes/dynamic.py` | 156 | Missing level-up feedback |
| `games/DuckHunt/game/modes/dynamic.py` | 477 | Unimplemented timed mode |

### 10. Documentation Gaps
- ~~No AMS event flow diagram~~ ✓ See `docs/architecture/AMS_ARCHITECTURE.md`
- ~~Architectural decisions not documented~~ ✓ See `docs/architecture/AMS_ARCHITECTURE.md`
- No calibration workflow documentation (step-by-step user guide)
- Step-by-step guide for adding new games exists but could be expanded

---

## Low Priority (Nice to Have)

### 11. Hardcoded Detection Thresholds
**File**: `ams/object_detection_backend.py`
**Issue**: Impact velocity (10.0 px/s), direction change (90.0°) hardcoded.
**Fix**: Make configurable via constructor or config.

### 12. Common Effect Patterns
**Issue**: Similar effect classes duplicated across games (PopEffect, etc.).
**Fix**: Extract to `games/common/effects/` if patterns mature.

### 13. Pasture WIP Directory
**Path**: `pasture/duckhunt-wip/`
**Issue**: Old WIP code that may confuse developers.
**Fix**: Archive or remove.

---

## Good Patterns to Spread

These patterns exist in parts of the codebase and should be adopted more widely.

### 1. YAML Game Mode Configuration (DuckHunt)

**Location**: `games/DuckHunt/modes/*.yaml`

**Pattern**: Game modes defined entirely in YAML files, not code:

```yaml
# modes/classic_ducks.yaml
name: "Classic Duck Hunt"
trajectory:
  algorithm: "bezier_3d"
  curvature_factor: 1.0
pacing:
  spawn_interval: 2.5
  target_lifetime: 6.0
levels:
  - level: 1
    target:
      size: 100.0
      speed: 80.0
    spawning:
      max_active: 1
```

**Benefits**:
- Magic numbers extracted from code
- Easy to tweak without code changes
- Non-programmers can create/tune game modes
- Version control shows config changes clearly
- Multiple modes without code duplication

**Candidates for adoption**:
- GrowingTargets: level progression could be YAML
- FruitSlice: difficulty presets could be YAML
- ManyTargets: progressive mode settings
- Containment: tempo presets

### 2. Pacing Presets (Common Infrastructure)

**Location**: `games/common/pacing.py`

**Pattern**: Named presets for device-speed tuning.

**Current** (Python dicts):
```python
PACING_PRESETS = {
    'archery': PacingPreset(spawn_interval=4.0, ...),
    'throwing': PacingPreset(spawn_interval=2.0, ...),
    'blaster': PacingPreset(spawn_interval=0.5, ...),
}
```

**Could be** (YAML):
```yaml
# games/common/pacing_presets.yaml
archery:
  description: "Slow cycle for bows, crossbows"
  spawn_interval: 4.0
  target_lifetime: 8.0
  combo_window: 10.0

throwing:
  description: "Medium cycle for darts, balls"
  spawn_interval: 2.0
  target_lifetime: 5.0
  combo_window: 5.0

blaster:
  description: "Fast cycle for Nerf, laser"
  spawn_interval: 0.5
  target_lifetime: 3.0
  combo_window: 2.0
```

**Benefits**:
- Games work across all input devices
- Single `--pacing` flag instead of many params
- Consistent experience terminology
- **YAML would allow**: custom presets without code changes, per-venue tuning

**Status**: Adopted by most games, but still Python dicts (candidate for YAML)

### 3. Internal State Pattern (ManyTargets, Grouping)

**Location**: `games/ManyTargets/game_mode.py`

**Pattern**: Private enum for complex state machines:

```python
class _InternalState(Enum):
    WAITING = auto()
    PLAYING = auto()
    ROUND_COMPLETE = auto()

class MyGame(BaseGame):
    def _get_internal_state(self) -> GameState:
        # Map complex internal states to simple external states
        return {
            _InternalState.WAITING: GameState.PLAYING,
            _InternalState.PLAYING: GameState.PLAYING,
            _InternalState.ROUND_COMPLETE: GameState.WON,
        }[self._internal_state]
```

**Benefits**:
- Clean separation of game-specific vs platform states
- External interface stays simple
- Internal complexity doesn't leak

**Status**: Documented in NEW_GAME_QUICKSTART.md ✓

---

## Completed Items

### ✓ Dynamic CLI Arguments (December 2024)
- **Issue**: `dev_game.py` had hardcoded game arguments.
- **Fix**: Two-phase argparse with dynamic loading from game classes.

### ✓ BaseGame Plugin Architecture (December 2024)
- **Issue**: Game metadata scattered in game_info.py modules.
- **Fix**: Moved to class attributes (NAME, DESCRIPTION, ARGUMENTS).

### ✓ Registry Discovery via Introspection (December 2024)
- **Issue**: Registry did source code introspection.
- **Fix**: Now uses `inspect.getmembers()` + `issubclass()` for proper discovery.

### ✓ Game Migrations to BaseGame (December 2024)

All games except DuckHunt now use BaseGame:
- BalloonPop
- Containment
- FruitSlice
- Grouping
- GrowingTargets
- ManyTargets

### ✓ Quick Fixes (December 2024)

- Deleted migration test artifacts (4 files)
- Fixed `'Games'` → `'games'` path in `ams/detection_backend.py`
- Deleted redundant root `models.py` (consolidated to `models/` package)

### ✓ AMS Architecture Documentation (December 2024)

- Created `docs/architecture/AMS_ARCHITECTURE.md`
- Documented detection backend comparison (mouse, laser, object)
- Added ADRs for key decisions (normalized coords, temporal state, etc.)
- Documented DuckHunt tech debt (ADR-004)
- Added "how to add a new backend" guide

### ✓ AMS Logging Infrastructure (December 2024)

- Added `logging` module to AMS package
- Created `docs/guides/AMS_DEVELOPER_GUIDE.md` with logging conventions
- Updated key modules: session.py, calibration.py, laser_detection_backend.py, object_detection_backend.py
- Established pattern: `logger = logging.getLogger('ams.modulename')`

---

## Statistics

| Metric | Count |
|--------|-------|
| Python files | 126 |
| Games | 8 |
| Test files | 12 (DuckHunt only) |
| TODO comments | 5 |
| Files needing logging | 12 |
| Games using BaseGame | 7/8 |

---

## Suggested Order of Work

1. **Quick wins** (< 1 hour each):
   - ~~Delete migration test files~~ ✓ Done
   - ~~Fix `Games` → `games` path~~ ✓ Done
   - ~~Consolidate models imports~~ ✓ Done (removed root `models.py`)

2. **Next sprint**:
   - Add logging infrastructure to AMS/calibration
   - Write tests for game registry
   - ~~Document DuckHunt architecture decision~~ ✓ Done (ADR-004 in AMS_ARCHITECTURE.md)

3. **Pattern spreading**:
   - Create `games/common/config_loader.py` for shared YAML parsing
   - Convert pacing presets to YAML (`games/common/pacing_presets.yaml`)
   - Add YAML config support to BaseGame for level progression
   - Extract GrowingTargets/FruitSlice/Containment settings to YAML

4. **Future**:
   - Migrate DuckHunt to BaseGame (or document why not)
   - Add comprehensive test coverage
   - Centralize configuration management
