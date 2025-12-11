# AMS Lua Scripting Guide

This guide covers writing Lua scripts for the AMS game engine. Lua provides extensibility for game mechanics that can't be expressed declaratively in YAML.

## Overview

AMS supports four types of Lua scripts, each with a specific purpose:

| Script Type | Directory | Purpose | Entry Function |
|-------------|-----------|---------|----------------|
| **Behaviors** | `ams/behaviors/lua/` | Entity lifecycle (update, spawn, destroy) | `on_update(entity_id, dt)` |
| **Collision Actions** | `ams/behaviors/collision_actions/` | Handle collisions between entities | `execute(entity_a_id, entity_b_id, modifier)` |
| **Generators** | `ams/behaviors/generators/` | Compute property values at spawn time | `generate(args)` |
| **Input Actions** | `ams/input_actions/` | Respond to user input events | `execute(x, y, args)` |

All scripts share access to the `ams` API but have different entry points and use cases.

---

## The `ams` API

All Lua scripts access game functionality through the global `ams` table. This sandboxed API provides safe access to entities, game state, and utilities.

### Entity Access

```lua
-- Position
ams.get_x(entity_id)              -- Get X position
ams.get_y(entity_id)              -- Get Y position
ams.set_x(entity_id, x)           -- Set X position
ams.set_y(entity_id, y)           -- Set Y position

-- Velocity
ams.get_vx(entity_id)             -- Get X velocity
ams.get_vy(entity_id)             -- Get Y velocity
ams.set_vx(entity_id, vx)         -- Set X velocity
ams.set_vy(entity_id, vy)         -- Set Y velocity

-- Dimensions
ams.get_width(entity_id)          -- Get entity width
ams.get_height(entity_id)         -- Get entity height

-- Visual
ams.get_sprite(entity_id)         -- Get sprite name
ams.set_sprite(entity_id, name)   -- Set sprite name
ams.get_color(entity_id)          -- Get color name
ams.set_color(entity_id, color)   -- Set color name

-- Health
ams.get_health(entity_id)         -- Get health value
ams.set_health(entity_id, hp)     -- Set health value

-- Lifecycle
ams.is_alive(entity_id)           -- Check if entity is alive
ams.destroy(entity_id)            -- Mark entity for destruction
```

### Custom Properties

Entities can store arbitrary key-value data that persists across frames:

```lua
-- Get/set custom properties
ams.get_prop(entity_id, "key")           -- Returns value or nil
ams.set_prop(entity_id, "key", value)    -- Store any value

-- Example: tracking state
ams.set_prop(entity_id, "hit_count", 0)
local hits = ams.get_prop(entity_id, "hit_count") or 0
ams.set_prop(entity_id, "hit_count", hits + 1)
```

### Behavior Configuration

Read config values defined in YAML's `behavior_config`:

```lua
-- ams.get_config(entity_id, behavior_name, key, default)
local speed = ams.get_config(entity_id, "bounce", "speed", 100)
local walls = ams.get_config(entity_id, "bounce", "walls", "all")
```

### Entity Spawning & Queries

```lua
-- Spawn new entity, returns entity_id
local id = ams.spawn(entity_type, x, y, vx, vy, width, height, color, sprite)

-- Use 0 for width/height to inherit from entity_type config
ams.spawn("duck_flying", x, y, vx, vy, 0, 0, "", "")

-- Query entities
local ids = ams.get_entities_of_type("brick")    -- By type name
local ids = ams.get_entities_by_tag("enemy")     -- By tag
local ids = ams.get_all_entity_ids()             -- All alive entities
local count = ams.count_entities_by_tag("duck")  -- Count by tag
```

### Game State

```lua
ams.get_screen_width()    -- Screen width in pixels
ams.get_screen_height()   -- Screen height in pixels
ams.get_score()           -- Current score
ams.add_score(points)     -- Add to score
ams.get_time()            -- Elapsed game time in seconds
```

### Events

```lua
ams.play_sound("shot")                        -- Play a sound
ams.schedule(delay, "callback_name", entity_id)  -- Schedule callback
```

### Math Utilities

```lua
-- Trigonometry
ams.sin(radians)
ams.cos(radians)
ams.sqrt(x)
ams.atan2(y, x)

-- Random
ams.random()                    -- Random float [0, 1)
ams.random_range(min, max)      -- Random float [min, max]

-- Utility
ams.clamp(value, min, max)      -- Clamp to range
```

### Debug

```lua
ams.log("message")    -- Print debug message to console
```

---

## Script Type 1: Behaviors

**Location:** `ams/behaviors/lua/`
**Purpose:** Control entity lifecycle - movement, animation, spawning logic

### Structure

```lua
--[[
behavior_name - brief description

Config options (from YAML):
  option1: type - description (default: value)
  option2: type - description

Usage in YAML:
  behaviors: [behavior_name]
  behavior_config:
    behavior_name:
      option1: value
]]

local behavior = {}

function behavior.on_spawn(entity_id)
    -- Called once when entity is created
    -- Initialize state, set up properties
    ams.set_prop(entity_id, "timer", 0)
end

function behavior.on_update(entity_id, dt)
    -- Called every frame
    -- dt = delta time in seconds since last frame
    local timer = ams.get_prop(entity_id, "timer") or 0
    timer = timer + dt
    ams.set_prop(entity_id, "timer", timer)
end

function behavior.on_destroy(entity_id)
    -- Called when entity is destroyed
    -- Spawn particles, play sounds, etc.
    ams.play_sound("explosion")
end

return behavior
```

### Lifecycle Hooks

| Hook | When Called | Use Cases |
|------|------------|-----------|
| `on_spawn(entity_id)` | Entity created | Initialize state, set properties |
| `on_update(entity_id, dt)` | Every frame | Movement, timers, AI logic |
| `on_destroy(entity_id)` | Entity destroyed | Particles, sounds, cleanup |

### Example: Gravity Behavior

```lua
-- gravity.lua
local gravity = {}

function gravity.on_update(entity_id, dt)
    local accel = ams.get_config(entity_id, "gravity", "acceleration", 500)
    local destroy_offscreen = ams.get_config(entity_id, "gravity", "destroy_offscreen", false)

    -- Apply gravity
    local vy = ams.get_vy(entity_id)
    vy = vy + accel * dt
    ams.set_vy(entity_id, vy)

    -- Move
    local y = ams.get_y(entity_id)
    y = y + vy * dt
    ams.set_y(entity_id, y)

    -- Destroy if off screen
    if destroy_offscreen and y > ams.get_screen_height() + 100 then
        ams.destroy(entity_id)
    end
end

return gravity
```

### YAML Usage

```yaml
entity_types:
  falling_object:
    behaviors: [gravity]
    behavior_config:
      gravity:
        acceleration: 800
        destroy_offscreen: true
```

### Inline Behaviors

For game-specific logic, behaviors can be defined inline in YAML:

```yaml
entity_types:
  spawner:
    behaviors:
      - lua: |
          local spawner = {}
          function spawner.on_update(entity_id, dt)
              local timer = ams.get_prop(entity_id, "timer") or 0
              timer = timer + dt
              if timer >= 2.0 then
                  ams.spawn("enemy", 400, 0, 0, 100, 0, 0, "", "")
                  timer = 0
              end
              ams.set_prop(entity_id, "timer", timer)
          end
          return spawner
```

---

## Script Type 2: Collision Actions

**Location:** `ams/behaviors/collision_actions/`
**Purpose:** Handle what happens when two entities collide

### Structure

```lua
--[[
action_name collision action

Brief description of what this action does.

Modifier options:
  option1: type - description (default: value)

Usage in game.yaml:
  collision_behaviors:
    type_a:
      type_b:
        action: action_name
        modifier:
          option1: value
]]

local action = {}

function action.execute(entity_a_id, entity_b_id, modifier)
    -- entity_a_id: The entity whose collision rule triggered
    -- entity_b_id: The entity it collided with
    -- modifier: Lua table of config from YAML (may be nil)

    local damage = 1
    if modifier and modifier.damage then
        damage = modifier.damage
    end

    local health = ams.get_health(entity_b_id)
    ams.set_health(entity_b_id, health - damage)

    if health - damage <= 0 then
        ams.destroy(entity_b_id)
        ams.add_score(100)
    end
end

return action
```

### Example: Take Damage

```lua
-- take_damage.lua
local take_damage = {}

function take_damage.execute(entity_a_id, entity_b_id, modifier)
    local damage = 1
    if modifier and modifier.damage then
        damage = modifier.damage
    end

    local health = ams.get_health(entity_b_id)
    local new_health = health - damage

    ams.set_health(entity_b_id, new_health)
    ams.play_sound("hit")

    if new_health <= 0 then
        local points = modifier and modifier.points or 100
        ams.add_score(points)
        ams.destroy(entity_b_id)
    end
end

return take_damage
```

### YAML Usage

```yaml
collision_behaviors:
  ball:
    brick:
      action: take_damage
      modifier:
        damage: 1
        points: 100

collisions:
  - [ball, brick]
```

### Inline Collision Actions

```yaml
collision_behaviors:
  projectile:
    enemy:
      action:
        lua: |
          local action = {}
          function action.execute(a_id, b_id, modifier)
              ams.destroy(b_id)
              ams.add_score(50)
              ams.play_sound("enemy_death")
          end
          return action
```

---

## Script Type 3: Generators

**Location:** `ams/behaviors/generators/`
**Purpose:** Compute property values at entity spawn time

### Structure

```lua
--[[
generator_name generator

Brief description.

Args:
  arg1: type - description
  arg2: type - description

Usage in YAML:
  x: {call: "generator_name", args: {arg1: value, arg2: value}}
]]

local generator = {}

function generator.generate(args)
    -- args: Lua table of arguments from YAML
    -- Returns: computed value

    local base = args.base or 0
    local offset = args.offset or 0
    return base + offset
end

return generator
```

### Example: Grid Position

```lua
-- grid_position.lua
local grid_position = {}

function grid_position.generate(args)
    local index = args.index or 0
    local start = args.start or 0
    local spacing = args.spacing or 0
    return start + (index * spacing)
end

return grid_position
```

### YAML Usage

Generators are called using `{call: "name", args: {...}}` syntax:

```yaml
levels:
  default:
    entities:
      - type: brick
        x: {call: "grid_position", args: {index: 0, start: 65, spacing: 75}}
        y: {call: "grid_position", args: {index: 0, start: 60, spacing: 30}}
      - type: brick
        x: {call: "grid_position", args: {index: 1, start: 65, spacing: 75}}
        y: {call: "grid_position", args: {index: 0, start: 60, spacing: 30}}
```

### Example: Color Blend

```lua
-- color_blend.lua
local color_blend = {}

function color_blend.generate(args)
    local colors = {"red", "orange", "yellow", "green", "blue", "purple"}
    local row = args.row or 0
    local index = (row % #colors) + 1
    return colors[index]
end

return color_blend
```

---

## Script Type 4: Input Actions

**Location:** `ams/input_actions/`
**Purpose:** Respond to user input events (clicks, touches)

### Structure

```lua
--[[
action_name input action

Brief description.

Args (from action_args in YAML):
  arg1: type - description
  arg2: type - description

Usage in YAML:
  global_on_input:
    action: action_name
    action_args:
      arg1: value
]]

local action = {}

function action.execute(x, y, args)
    -- x, y: Input position in screen coordinates
    -- args: Lua table from action_args (may be nil)

    local sound = args and args.sound or "click"
    ams.play_sound(sound)
end

return action
```

### Example: Spawn Particles

```lua
-- spawn_particles.lua
local action = {}

function action.execute(x, y, args)
    local particle_type = args and args.type or "particle"
    local count = args and args.count or 3

    for i = 1, count do
        local vx = ams.random_range(-50, 50)
        local vy = ams.random_range(-100, -50)
        ams.spawn(particle_type, x, y, vx, vy, 0, 0, "", "")
    end
end

return action
```

### YAML Usage

```yaml
# Global input action (fires on any input)
global_on_input:
  action: spawn_particles
  action_args:
    type: spark
    count: 5

# Or use built-in play_sound action
global_on_input:
  action: play_sound
  action_args:
    sound: shot
```

### Inline Input Actions

```yaml
global_on_input:
  action:
    lua: |
      local action = {}
      function action.execute(x, y, args)
          ams.log("Click at " .. x .. ", " .. y)
          ams.play_sound("click")
      end
      return action
```

---

## Built-in Behaviors

These behaviors are included with AMS:

| Behavior | Purpose | Key Config |
|----------|---------|------------|
| `animate` | Cycle animation frames | `frames`, `fps` |
| `bounce` | Move with velocity, bounce off walls | `walls`, `min_y`, `max_y` |
| `gravity` | Apply downward acceleration | `acceleration`, `destroy_offscreen` |
| `descend` | Move downward at constant speed | `speed` |
| `oscillate` | Move side-to-side | `speed`, `range` |
| `paddle` | Input-controlled paddle | `speed` |
| `projectile` | Move in direction, destroy off-screen | `speed` |
| `shoot` | Periodically spawn projectiles | `interval`, `projectile_type` |

---

## Best Practices

### 1. Use Config for Tunable Values

```lua
-- Good: Configurable from YAML
local speed = ams.get_config(entity_id, "my_behavior", "speed", 100)

-- Avoid: Hardcoded values
local speed = 100
```

### 2. Initialize State in on_spawn

```lua
function behavior.on_spawn(entity_id)
    ams.set_prop(entity_id, "timer", 0)
    ams.set_prop(entity_id, "state", "idle")
end
```

### 3. Use Properties for Per-Entity State

```lua
-- Each entity has its own timer
local timer = ams.get_prop(entity_id, "timer") or 0
timer = timer + dt
ams.set_prop(entity_id, "timer", timer)
```

### 4. Prefix Internal Properties with Underscore

```lua
-- Internal state (not for external use)
ams.set_prop(entity_id, "_internal_timer", 0)

-- Public state (may be read by rendering)
ams.set_prop(entity_id, "frame", 1)
```

### 5. Handle nil Modifier/Args

```lua
function action.execute(a_id, b_id, modifier)
    -- Always check for nil
    local damage = 1
    if modifier and modifier.damage then
        damage = modifier.damage
    end
end
```

### 6. Use dt for Frame-Independent Movement

```lua
-- Good: Same speed regardless of framerate
local x = ams.get_x(entity_id)
x = x + speed * dt
ams.set_x(entity_id, x)

-- Bad: Speed varies with framerate
x = x + speed
```

---

## Sandbox Security

Lua scripts run in a sandboxed environment with restricted access:

**Allowed:**
- `ams.*` API functions
- Basic Lua: `math`, `string`, `table`, `pairs`, `ipairs`, `type`, `tostring`, `tonumber`
- Control flow, functions, tables, local variables

**Blocked:**
- File system access (`io`, `os`)
- Network access
- Loading external code (`require`, `dofile`, `loadfile`)
- Raw Python object access
- `debug` library
- `_G` modification

This ensures games are safe to run and can be ported to web browsers (WASM) in the future.

---

## Debugging Tips

1. **Use `ams.log()`** for debug output:
   ```lua
   ams.log("Entity " .. entity_id .. " at " .. ams.get_x(entity_id))
   ```

2. **Check entity exists** before accessing:
   ```lua
   if ams.is_alive(entity_id) then
       -- Safe to access
   end
   ```

3. **Watch for nil values**:
   ```lua
   local value = ams.get_prop(entity_id, "key") or default_value
   ```

4. **Print config values** to verify they're being read:
   ```lua
   local speed = ams.get_config(entity_id, "behavior", "speed", 100)
   ams.log("Speed config: " .. tostring(speed))
   ```
