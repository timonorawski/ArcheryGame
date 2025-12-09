"""
AMS Web Controller - Mobile interface for game control.

Provides a FastAPI server with WebSocket support for real-time
state sync between the AMS session and mobile devices.
"""

from .server import WebController, GameState, SessionInfo

__all__ = ["WebController", "GameState", "SessionInfo"]
