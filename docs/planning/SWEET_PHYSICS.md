# Sweet Physics - Implementation Plan

Cut the Rope-style physics puzzle game where you shoot targets to manipulate physics elements and guide an object to a goal.

## Core Concept

Physics puzzle game where projectile-based interaction replaces touchscreen swipes. Each shot is a commitment with physical constraints - the economy of limited arrows transforms casual puzzling into deliberate decision-making.

## Gameplay Loop

1. Level presents: suspended object, goal location, obstacles, collectibles (stars)
2. Player studies physics setup - ropes, bubbles, air cushions, mechanisms
3. Player shoots targets to trigger physics changes
4. Object moves according to physics
5. Success = object reaches goal; bonus = collect stars along the way

## Skill Layers (Progressive Depth)

| Layer | Challenge | Metric |
|-------|-----------|--------|
| Basic | Get object to goal | Completion |
| Precision | Collect stars en route | Star count |
| Economy | Fewer shots = better | Shot count |
| Timing | Speed bonus / time pressure | Time |

## Physics Elements

### Targetable Elements (Things You Can Hit)

| Element | Visual | Behavior When Hit | Physics |
|---------|--------|-------------------|---------|
| **Rope** | Line with attachment points | Cuts at hit point, releases tension | Segmented physics body |
| **Bubble** | Translucent sphere | Pops, releases floating object | Applies upward force while inside |
| **Air Cushion** | Fan/vent graphic | Toggles on/off, blows object | Directional force field |
| **Button/Trigger** | Target circle | Activates linked mechanism | State toggle |
| **Bumper** | Bouncy surface | Temporarily energized | Coefficient of restitution boost |

### Passive Elements (Environment)

| Element | Behavior |
|---------|----------|
| **Wall** | Solid collision |
| **Platform** | One-way or solid surface |
| **Spikes** | Instant fail on contact |
| **Portal** | Teleports object to linked portal |
| **Conveyor** | Moves object along surface |
| **Gravity Zone** | Altered gravity direction/strength |

### Collectibles

| Element | Behavior |
|---------|----------|
| **Star** | Collected on contact, 3 per level typical |
| **Bonus Item** | Optional score multiplier |

## The Candy (Payload Object)

- Circular physics body with realistic collision
- Affected by gravity, friction, bouncing
- Visual: Candy, ball, acorn, or themed object
- States: Normal, Floating (in bubble), Falling, Goal Reached, Lost

## Level Structure

```yaml
name: "Swing and Drop"
author: "AMS Team"
difficulty: 2  # 1-5 scale
description: "Cut the right rope at the right time"

# Star requirements for ratings
stars:
  one_star: { complete: true }
  two_star: { complete: true, shots: 4 }
  three_star: { complete: true, shots: 3, time: 15 }

# Arrow budget (null = unlimited)
arrow_budget: 5

# Physics settings
physics:
  gravity: [0, 980]  # pixels/sec^2
  air_resistance: 0.99

# Play area bounds
bounds:
  width: 1280
  height: 720
  margin: 50  # fail zone outside bounds

# Level elements
elements:
  # The payload
  - type: candy
    position: [640, 100]
    radius: 25

  # Goal
  - type: goal
    position: [640, 600]
    radius: 60

  # Ropes
  - type: rope
    anchor: [400, 50]
    attachment: candy  # attaches to candy
    segments: 8
    length: 150

  - type: rope
    anchor: [880, 50]
    attachment: candy
    segments: 8
    length: 150

  # Stars
  - type: star
    position: [300, 300]

  - type: star
    position: [640, 400]

  - type: star
    position: [980, 300]

  # Obstacles
  - type: platform
    start: [200, 500]
    end: [500, 520]

  - type: spikes
    position: [100, 650]
    width: 200
```

## Physics Engine

### Option 1: Pymunk (Recommended)
- Python bindings for Chipmunk2D
- Battle-tested 2D physics
- Good documentation
- Handles ropes via pin joints + segments

```python
import pymunk

# Create space
space = pymunk.Space()
space.gravity = (0, 980)

# Create candy body
candy_body = pymunk.Body(1, pymunk.moment_for_circle(1, 0, 25))
candy_shape = pymunk.Circle(candy_body, 25)
space.add(candy_body, candy_shape)

# Create rope as chain of segments
def create_rope(space, anchor, end_body, length, segments):
    segment_length = length / segments
    prev_body = None

    for i in range(segments):
        # Create segment body
        body = pymunk.Body(0.1, pymunk.moment_for_segment(0.1, (0,0), (0, segment_length)))
        # ... add joints between segments
```

### Option 2: Custom Simple Physics
- Roll our own for subset of features
- More control, less dependency
- Risk: edge cases, stability issues

**Recommendation**: Use Pymunk. Physics is hard to get right, and we want the puzzles to feel good.

## Architecture

```
games/SweetPhysics/
├── __init__.py
├── config.py              # Constants, physics defaults
├── game_info.py           # Factory
├── game_mode.py           # Main game class
├── input/                 # Standard input re-exports
│   ├── __init__.py
│   ├── input_manager.py
│   └── sources/
│       ├── __init__.py
│       └── mouse.py
├── physics/
│   ├── __init__.py
│   ├── world.py           # Physics world wrapper
│   ├── elements.py        # Physics element classes
│   └── collision.py       # Collision handlers
├── elements/
│   ├── __init__.py
│   ├── base.py            # Base element class
│   ├── rope.py            # Rope with cut detection
│   ├── bubble.py          # Floating bubble
│   ├── air_cushion.py     # Directional air flow
│   ├── button.py          # Trigger mechanism
│   ├── platform.py        # Static/moving platforms
│   ├── goal.py            # Win zone
│   ├── star.py            # Collectible
│   └── candy.py           # Payload object
├── rendering/
│   ├── __init__.py
│   ├── renderer.py        # Main rendering coordinator
│   └── element_renderers.py  # Per-element rendering
├── levels/
│   ├── __init__.py
│   ├── loader.py          # YAML level loader
│   ├── schema.py          # Level validation
│   └── levels/            # Actual level files
│       ├── 01_tutorial_drop.yaml
│       ├── 02_tutorial_swing.yaml
│       ├── 03_two_ropes.yaml
│       └── ...
└── ui/
    ├── __init__.py
    ├── hud.py             # Score, stars, shots remaining
    └── level_select.py    # Level chooser (reuse pattern from Containment)
```

## Implementation Phases

### Phase 1: Physics Foundation
1. Set up Pymunk integration
2. Implement basic world with gravity
3. Create candy physics body
4. Add static walls/bounds
5. Test: candy falls and bounces

### Phase 2: Rope System
1. Implement rope as chain of segments
2. Attach rope to candy
3. Implement rope cutting via hit detection
4. Test: cut rope, candy swings and falls

### Phase 3: Goal and Win Condition
1. Implement goal zone with collision detection
2. Add win state when candy reaches goal
3. Add fail state when candy leaves bounds
4. Test: complete simple "cut to drop into goal" level

### Phase 4: Stars and Scoring
1. Implement star collectibles
2. Track collected stars
3. Add shot counting
4. Implement star rating system (1-3 stars)
5. Test: collect stars while reaching goal

### Phase 5: Level System
1. Implement YAML level loader
2. Create level validation schema
3. Build tutorial levels (3-5 levels)
4. Implement level progression
5. Add level select UI

### Phase 6: Additional Elements
1. Bubbles (float mechanic)
2. Air cushions (directional force)
3. Buttons/triggers (mechanism activation)
4. Moving platforms
5. Portals (teleportation)

### Phase 7: Polish
1. Visual feedback (cut animations, star collection)
2. Sound design hooks
3. Difficulty tuning
4. Additional levels (10-20 total)
5. Performance optimization

## Key Technical Challenges

### 1. Rope Cutting
Need to detect where a hit intersects a rope and split it at that point.

```python
def check_rope_cut(rope: Rope, hit_x: float, hit_y: float, radius: float) -> bool:
    """Check if hit point intersects any rope segment."""
    for segment in rope.segments:
        if point_near_segment(hit_x, hit_y, segment, radius):
            rope.cut_at_segment(segment)
            return True
    return False
```

### 2. Bubble Physics
Bubbles need to:
- Capture candy when it enters
- Apply upward force (float)
- Pop when hit, releasing candy

```python
class Bubble:
    def update(self, dt):
        if self.contains_candy:
            # Apply upward force
            self.candy.body.apply_force_at_local_point((0, -FLOAT_FORCE))

    def on_hit(self, hit_x, hit_y):
        self.pop()
        if self.contains_candy:
            self.release_candy()
```

### 3. Timing Windows
Some puzzles require precise timing - cut at the right moment in swing arc.

```python
# Visual hint: subtle glow when candy is at optimal cut point
def get_swing_phase(rope: Rope) -> float:
    """Return 0-1 indicating position in swing cycle."""
    velocity = rope.end_body.velocity
    # Calculate based on velocity direction vs gravity
    ...
```

### 4. Hit Detection on Physics Objects
Need to map screen coordinates to physics world and detect which element was hit.

```python
def find_hit_element(hit_x: float, hit_y: float) -> Optional[Element]:
    """Find targetable element at hit position."""
    # Check ropes first (thin, need generous hitbox)
    for rope in self.ropes:
        if rope.check_hit(hit_x, hit_y, HIT_RADIUS):
            return rope

    # Check other targetable elements
    for element in self.targetable_elements:
        if element.check_hit(hit_x, hit_y):
            return element

    return None
```

## Quiver Integration

Arrow budget creates meaningful puzzle constraints:

```yaml
# Generous budget - focus on completion
arrow_budget: 10

# Tight budget - every shot matters
arrow_budget: 3

# Exactly enough - requires optimal solution
arrow_budget: null  # Level defines optimal, any solution OK
stars:
  three_star: { shots: 2 }  # But 3-star requires efficiency
```

Retrieval pause becomes natural puzzle phase:
- Player shoots, watches physics play out
- Retrieval gives time to observe and plan next shot
- Some levels may require multiple "rounds" by design

## Visual Design

### Style Options

1. **Candy/Cute** (Om Nom style)
   - Bright colors, rounded shapes
   - Candy as payload, cute creature as goal
   - Playful, accessible feel

2. **Abstract/Geometric**
   - Clean lines, pure shapes
   - Focus on physics clarity
   - Minimalist aesthetic

3. **Nature Theme**
   - Acorn → Squirrel
   - Fish through water currents
   - Organic, calming feel

**Recommendation**: Start with Abstract/Geometric for clarity, add themed asset packs later.

### Visual Feedback

| Action | Feedback |
|--------|----------|
| Rope cut | Snap animation, rope ends fly apart |
| Bubble pop | Burst particles, float force dissipates |
| Star collect | Sparkle effect, UI counter updates |
| Goal reached | Celebration animation, stars tally |
| Fail (out of bounds) | Fade out, retry prompt |
| Fail (spikes) | Flash red, retry prompt |

## Level Design Principles

1. **Clear visual language** - Each element type instantly recognizable
2. **One new concept per level** - Introduce mechanics gradually
3. **Multiple solutions** - Emergent, not scripted paths
4. **Stars as mastery** - Completion easy, 3-star hard
5. **Aha moments** - Reward clever thinking
6. **Generous at first** - Early levels forgiving, later levels demanding

## Tutorial Sequence

| Level | Concept | Elements |
|-------|---------|----------|
| 1 | Basic drop | 1 rope, goal directly below |
| 2 | Swing timing | 1 rope, goal offset, need swing |
| 3 | Two ropes | 2 ropes, cut sequence matters |
| 4 | Stars intro | Ropes + stars in path |
| 5 | Bubbles | Rope + bubble to float over obstacle |
| 6 | Air cushion | Float + redirect with air |
| 7 | Combination | Multiple mechanics together |

## Comparison to Other AMS Games

| Aspect | Containment | Love-O-Meter | Sweet Physics |
|--------|-------------|--------------|---------------|
| Pressure | Reactive, real-time | Tempo-based | Self-paced |
| Thinking | Adaptive | None (flow) | Planning |
| Pacing | Frantic | Relentless | Deliberate |
| Skill type | Tracking | Speed/form | Precision + timing |
| Archery training | Snap shooting | Tempo/stamina | Patience, held draw |

## Open Questions

1. **Physics library**: Pymunk vs custom? (Recommendation: Pymunk)
2. **Level editor**: Build one or YAML-only? (Start YAML, editor later)
3. **Difficulty curve**: How many tutorial levels before challenge?
4. **Theming**: Start abstract or themed? (Abstract first)
5. **Trajectory preview**: Show predicted path after cut? (Optional easy mode)

## Success Metrics

- [ ] "One more level" compulsion
- [ ] Visible improvement in efficiency over replays
- [ ] Puzzle solutions feel earned, not lucky
- [ ] 3-star ratings feel achievable with practice
- [ ] Physics feels consistent and fair
- [ ] Archery value: patience and timing training

## Dependencies

```
pymunk>=6.0.0  # 2D physics engine
```

## Related Documents

- [GAME_IDEAS.md](GAME_IDEAS.md) - Original concept (#33)
- [Containment Levels](../games/Containment/levels/) - YAML level pattern reference
- [BaseGame](../games/common/base_game.py) - Game architecture

---

## Implementation Checklist

### Phase 1: Foundation
- [ ] Add pymunk to requirements.txt
- [ ] Create directory structure
- [ ] Implement PhysicsWorld wrapper
- [ ] Create Candy physics body
- [ ] Add gravity and bounds
- [ ] Test basic falling/bouncing

### Phase 2: Ropes
- [ ] Implement Rope class with segments
- [ ] Rope-to-candy attachment
- [ ] Hit detection on rope segments
- [ ] Rope cutting mechanic
- [ ] Rope rendering (segmented line)

### Phase 3: Core Loop
- [ ] Goal zone implementation
- [ ] Win/lose state detection
- [ ] Basic game mode class
- [ ] Single hardcoded test level
- [ ] Input handling (hit → cut)

### Phase 4: Levels
- [ ] YAML level schema
- [ ] Level loader
- [ ] 3 tutorial levels
- [ ] Level completion tracking
- [ ] Star collection

### Phase 5: Polish
- [ ] Visual feedback
- [ ] UI (shots, stars, level name)
- [ ] Level select screen
- [ ] 5+ additional levels
- [ ] Difficulty tuning

### Phase 6: Extended Elements
- [ ] Bubbles
- [ ] Air cushions
- [ ] Buttons/triggers
- [ ] Moving platforms
- [ ] Portals (stretch goal)
