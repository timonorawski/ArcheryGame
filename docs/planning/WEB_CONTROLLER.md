AMS Web Controller (Mobile Interface)**

**Core Concept:**
Side-channel web interface for game control, configuration, and monitoring. Phone becomes the control surface when you're at the range with bow in hand - no keyboard/mouse needed.

**The Problem:**
At the range, you're standing at distance from the projection surface, bow in hand. Walking to a computer to adjust settings, start rounds, or pause breaks flow. Phone in pocket is always accessible.

**The Solution:**
Lightweight web app served by the AMS session. Scan QR code on projection, phone connects, instant control surface. No app install, works on any device with a browser.

**Primary Use Cases:**

*Solo Archer:*
- Start/pause/resume rounds
- Adjust difficulty mid-session
- Trigger retrieval pause
- View stats between rounds
- Swap games/levels without touching computer

*Coach/Parent:*
- Watch player's session stats live
- Adjust difficulty in real-time to keep kid in flow
- Spawn challenges manually
- Control pacing without interrupting

*Party Host:*
- Manage multiplayer lobby
- Switch games for variety
- Control music/sound
- Reset between players

**Interface Principles:**

*Minimal, glanceable:*
- Big touch targets (using with one hand, maybe holding blaster)
- Essential info only
- No scrolling for primary actions
- Works in bright outdoor light

*Context-aware:*
- Shows different controls based on game state
- Playing: pause, difficulty adjust
- Paused: resume, change game, view stats
- Between rounds: level select, settings
- Retrieval: countdown, ready button

*Low latency feel:*
- Actions feel instant
- Visual confirmation of commands sent
- Graceful handling of connection hiccups

**Screen Concepts:**

*Home / Connection:*
```
┌─────────────────────────┐
│                         │
│      [QR CODE]          │
│                         │
│   Scan to connect       │
│   or enter: 192.168.x.x │
│                         │
└─────────────────────────┘
```

*Now Playing:*
```
┌─────────────────────────┐
│  CONTAINMENT            │
│  Level: Connect Dots    │
│  Time: 1:34             │
│                         │
│  ┌─────┐    ┌─────┐     │
│  │PAUSE│    │ END │     │
│  └─────┘    └─────┘     │
│                         │
│  Difficulty: ███░░ 3/5  │
│  [<]              [>]   │
│                         │
└─────────────────────────┘
```

*Game Select:*
```
┌─────────────────────────┐
│  SELECT GAME            │
│                         │
│  ┌───────────────────┐  │
│  │ 🎯 Containment    │  │
│  └───────────────────┘  │
│  ┌───────────────────┐  │
│  │ 🌡️ Love-O-Meter   │  │
│  └───────────────────┘  │
│  ┌───────────────────┐  │
│  │ 🏃 Trail Blazer   │  │
│  └───────────────────┘  │
│  ┌───────────────────┐  │
│  │ 🍬 Sweet Physics  │  │
│  └───────────────────┘  │
│                         │
└─────────────────────────┘
```

*Level Browser (within game):*
```
┌─────────────────────────┐
│  CONTAINMENT LEVELS     │
│  [<- Back]              │
│                         │
│  Core:                  │
│   • Classic Mode        │
│   • Connect the Dots    │
│   • All Hit Modes       │
│                         │
│  Community:             │
│   • Chaos Spiral        │
│   • Zen Garden          │
│   • Speed Run 1         │
│                         │
│  [+ Import Level]       │
└─────────────────────────┘
```

*Live Stats (Coach View):*
```
┌─────────────────────────┐
│  SESSION STATS          │
│                         │
│  Hits: 47  Misses: 12   │
│  Accuracy: 79%          │
│                         │
│  Current streak: 8      │
│  Best streak: 14        │
│                         │
│  Session time: 12:34    │
│  Active shooting: 8:21  │
│                         │
│  [Detailed View ->]     │
└─────────────────────────┘
```

*Settings Panel:*
```
┌─────────────────────────┐
│  SETTINGS               │
│                         │
│  Pacing:                │
│  [Archery] Throw  Blast │
│                         │
│  Sound:                 │
│  [On] Off               │
│                         │
│  Palette:               │
│  [Auto] High Contrast   │
│                         │
│  Quiver Size:           │
│  [  6  ] [-] [+]        │
│                         │
└─────────────────────────┘
```

**Features by Priority:**

*Must Have (v1):*
- Connect via QR/URL
- Start/pause/resume
- Game selection
- Level selection within game
- Basic stats display

*Should Have (v2):*
- Live difficulty adjustment
- Retrieval trigger/ready
- Pacing preset switch
- Sound control
- Session stats

*Nice to Have (v3):*
- Coach mode with player monitoring
- Level import from URL/file
- Multiplayer lobby management
- Replay/history viewer
- Custom level creator (simplified)

**Connection Model:**

- AMS session runs lightweight HTTP server
- Websocket for real-time state sync
- Phone and game see same state
- Commands are requests, game is authoritative
- Graceful reconnection if signal drops

**State Sync:**
Phone needs to know:
- Current game + level
- Game state (playing/paused/retrieval/ended)
- Current score/stats
- Available games/levels
- Current settings

Game needs to accept:
- Start/pause/resume commands
- Level load requests
- Settings changes
- Difficulty adjustments

**Security (Local Network):**
- No auth for local network (trusted environment)
- Optional PIN for public wifi scenarios
- No internet connectivity required
- All traffic stays on local network

**Party Mode Considerations:**

Multiple phones connecting:
- All see same state
- Any can control (or designate controller)
- Spectator mode option (view only)
- Player queue for turn-taking games

**Technical Boundaries:**
The interface controls the session, not the game directly. Commands go through AMS, which routes to current game appropriately. This keeps games ignorant of the controller - they just receive the same events they would from keyboard/CLI.

**Design Language:**
- Match game palettes where possible
- Dark mode default (outdoor visibility, night sessions)
- High contrast, accessible
- Playful but not childish (adults use it too)
- Consistent with projected game aesthetic

**Future Possibilities:**

*Second Screen:*
- Phone shows different info than projection
- Personal stats while projection shows game
- Private feedback for competitive play

*AR Layer:*
- Camera preview with projected game overlay
- Line up shots before walking to position
- Range finding / calibration assist

*Voice Control:*
- "Pause" / "Resume" / "Next level"
- Useful when hands full
- Accessibility option

*Haptic Feedback:*
- Vibrate on hit registration
- Rhythm feedback for Love-O-Meter
- Subtle confirmation of actions