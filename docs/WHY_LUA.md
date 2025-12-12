# Why This Architecture: Lua as the Load-Bearing Layer

The choice to centralize all entity logic in Lua is intentional and foundational. It is not a convenience, it is a **keystone decision** that shapes every aspect of YAMS’ engine design. This section explains the reasoning behind this architecture.

## 1. Safety and Sandboxing

- Lua runs in a confined VM, preventing scripts from touching Python internals, the DOM, or system resources directly.
- This ensures that untrusted or experimental scripts cannot crash the engine or corrupt game state.
- The sandbox acts as a “firewall” around core engine systems, isolating side effects and limiting the blast radius of bugs.

## 2. Determinism and Rollback

- Rollback, re-simulation, and networked prediction require deterministic updates.
- By funneling all game logic through Lua, every frame’s behavior is reproducible.
- Seeded random number generators, fixed timestep updates, and entity-local state ensure that replaying a sequence of events produces the same result across frames and platforms.

## 3. Portability and Consistency

- Native deployment uses Lua 5.4 (via Lupa); browser deployment uses Lua 5.3 via Fengari.
- The same subroutine code runs identically in both environments, allowing a single source of truth for behaviors, collision actions, and generators.
- Differences between runtimes are minimal, confined to IO or rendering layers, not core game logic.

## 4. Clear Separation of Concerns

- GameEngine handles physics, timing, collisions, and rendering.
- Lua handles **entity behaviors, property generation, and collision actions**.
- This clear boundary makes reasoning about state, debugging, and testing simpler: Python manages the “world,” Lua manages the “actors.”

## 5. Extensibility and Hot-Loading

- Lua scripts can be added, modified, or replaced without recompiling the engine.
- Inline YAML scripts or `.lua.yaml` files enable rapid prototyping, reusable behaviors, and modular game design.
- Developers can experiment freely while the engine maintains a consistent runtime contract.

## 6. Performance vs Correctness

- In the browser, Lua (via Fengari) is slower than native LuaJIT, but correctness and stability are prioritized over micro-optimizations.
- Future WASM Lua implementations may improve performance, but the architecture ensures any changes are backward-compatible.

## 7. Security for Untrusted Content

- Running user-provided scripts in Lua isolates potentially unsafe operations.
- In browser deployment, this layered model (Python WASM → JS → Lua interpreter via Fengari) acts as a security boundary, enforcing a principle of **least privilege**.
- The engine can safely execute experimental game logic without risking the host environment.

## 8. Radical Inspectability (Safety + Pedagogy)

YAMS is built for two audiences who must never be asked to “just trust me”:

- **Strangers on the internet** (sharing games)  
- **Children and learners** (understanding how things work)

Lua as the load-bearing layer delivers **inspectability** on both axes.

### Safety Through Visibility (“Sharing Fries”)

When a child receives a game from a friend (or from the public gallery), the entire behavior of that game is contained in plain-text Lua + YAML.

There is no compiled blob, no minified JavaScript, no WebAssembly black box.

A parent, teacher, or even a cautious 10-year-old can:

- Open `behaviors/gravity.lua.yaml` → instantly see how gravity is implemented  
- Search the entire game folder for `spawn`, `destroy`, `play_sound`, or `require`  
- Verify in < 30 seconds that nothing phones home, nothing tries to access the webcam, nothing is hidden

We call this **“sharing fries”** — you can look at the fries before you eat them.  
No trust required. Only inspection.

### Pedagogy Through Transparency

When a child wants to learn **why** the ball bounces that way, they don’t need to open a node graph, reverse-engineer a blueprint, or guess at inspector properties.

They open `collision_actions/bounce.lua.yaml`  
→ read 25 lines of clear, commented Lua  
→ change one number  
→ instantly see the effect

Every piece of game logic is:

- Human-scale (most behaviors < 60 lines)  
- Self-contained (one file = one concept)  
- Self-documenting (description, examples, config schema in the same file)  
- Directly editable in real time

Learning is no longer “watch a tutorial.”  
It is **“open the file and play with it.”**

The same property that makes the engine safe for strangers makes it the most powerful teaching tool imaginable.

Inspectability is not a side effect.  
It is the final, and perhaps most important, reason Lua is the load-bearing layer.

The yam insists on being understood.

**Conclusion**

Lua is not a peripheral convenience; it is the **load-bearing layer** of YAMS’ architecture.  
It enables:

- deterministic rollback and simulation  
- cross-platform consistency  
- safe execution of untrusted scripts  
- radical inspectability for both security and learning  
- rapid, modular game development

The yam has spoken.
