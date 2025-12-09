#!/usr/bin/env python3
"""
Test script for the AMS Web Controller.

Run this to verify the web controller server works:
    python -m ams.web_controller.test_server

Then open http://localhost:8080 in your browser.
"""

import time
import random
from .server import WebController, GameState, SessionInfo


# Global state for simulated session
class SimulatedSession:
    def __init__(self):
        self.backend = "mouse"
        self.calibrated = False
        self.current_game = None
        self.game_state = "idle"
        self.score = 0
        self.hits = 0
        self.misses = 0
        self.start_time = None
        self.paused_time = 0

    def set_backend(self, backend):
        self.backend = backend
        # Mouse is always "calibrated"
        self.calibrated = (backend == "mouse")
        print(f"Backend set to: {backend}")
        return {"backend": backend}

    def calibrate(self):
        print("Calibration requested (simulated)...")
        time.sleep(0.5)  # Simulate calibration
        self.calibrated = True
        print("Calibration complete!")
        return {"calibrated": True}

    def launch_game(self, game):
        print(f"Launching game: {game}")
        self.current_game = game
        self.game_state = "playing"
        self.score = 0
        self.hits = 0
        self.misses = 0
        self.start_time = time.time()
        self.paused_time = 0
        return {"game": game, "status": "launched"}

    def stop_game(self):
        print(f"Stopping game: {self.current_game}")
        self.current_game = None
        self.game_state = "idle"
        return {"status": "stopped"}

    def pause(self):
        if self.game_state == "playing":
            self.game_state = "paused"
            print("Game paused")
        return {"state": self.game_state}

    def resume(self):
        if self.game_state in ("paused", "retrieval"):
            self.game_state = "playing"
            print("Game resumed")
        return {"state": self.game_state}

    def retrieval(self):
        if self.game_state in ("playing", "paused"):
            self.game_state = "retrieval"
            print("Retrieval mode")
        return {"state": self.game_state}

    def get_elapsed_time(self):
        if self.start_time is None:
            return 0
        if self.game_state == "idle":
            return 0
        return time.time() - self.start_time - self.paused_time


def main():
    print("=" * 60)
    print("AMS Web Controller Test")
    print("=" * 60)

    session = SimulatedSession()

    # Create and start web controller
    controller = WebController(host="0.0.0.0", port=8080)

    # Register command handlers
    controller.register_command("set_backend", lambda p: session.set_backend(p.get("backend", "mouse")))
    controller.register_command("calibrate", lambda p: session.calibrate())
    controller.register_command("launch_game", lambda p: session.launch_game(p.get("game")))
    controller.register_command("stop_game", lambda p: session.stop_game())
    controller.register_command("pause", lambda p: session.pause())
    controller.register_command("resume", lambda p: session.resume())
    controller.register_command("retrieval", lambda p: session.retrieval())

    controller.start()

    print(f"\nWeb controller running at: {controller.url}")
    print("Open this URL on your phone or browser to test.")
    print("\nSimulating game state updates...")
    print("Press Ctrl+C to stop.\n")

    # Set initial session info
    available_games = ["Containment", "Love-O-Meter", "Sweet Physics", "Duck Hunt"]

    try:
        while True:
            # Simulate game activity
            if session.game_state == "playing":
                # Random hits/misses while playing
                if random.random() < 0.3:
                    if random.random() < 0.7:
                        session.hits += 1
                        session.score += random.randint(100, 500)
                    else:
                        session.misses += 1

            # Update session info
            controller.update_session_info(SessionInfo(
                available_games=available_games,
                current_game=session.current_game,
                detection_backend=session.backend,
                calibrated=session.calibrated,
            ))

            # Update game state
            controller.update_game_state(GameState(
                game_name=session.current_game or "No Game",
                level_name="Level 1" if session.current_game else "",
                state=session.game_state,
                score=session.score,
                time_elapsed=session.get_elapsed_time(),
                hits=session.hits,
                misses=session.misses,
            ))

            # Show status
            print(f"\r[{session.get_elapsed_time():6.1f}s] State: {session.game_state:10} | "
                  f"Game: {session.current_game or 'None':15} | "
                  f"Score: {session.score:5} | "
                  f"Connections: {controller.connection_count}", end="", flush=True)

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\nStopping web controller...")
        controller.stop()
        print("Done!")


if __name__ == "__main__":
    main()
