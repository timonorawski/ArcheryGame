"""
Base element class for Sweet Physics game objects.
"""
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import pygame
import pymunk

from games.SweetPhysics.physics.world import PhysicsWorld


class Element(ABC):
    """
    Base class for all game elements.

    Elements can be targetable (can be hit/cut) or passive (environment).
    """

    def __init__(self, world: PhysicsWorld):
        """
        Initialize element.

        Args:
            world: Physics world this element belongs to
        """
        self._world = world
        self._active = True

    @property
    def active(self) -> bool:
        """Whether this element is active in the game."""
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        self._active = value

    @property
    def targetable(self) -> bool:
        """Whether this element can be hit/targeted."""
        return False

    def check_hit(self, x: float, y: float, radius: float) -> bool:
        """
        Check if a hit at (x, y) affects this element.

        Args:
            x: Hit X coordinate
            y: Hit Y coordinate
            radius: Hit radius

        Returns:
            True if hit affects this element
        """
        return False

    def on_hit(self, x: float, y: float) -> bool:
        """
        Handle being hit at (x, y).

        Args:
            x: Hit X coordinate
            y: Hit Y coordinate

        Returns:
            True if hit was processed (consumed)
        """
        return False

    def update(self, dt: float) -> None:
        """
        Update element state.

        Args:
            dt: Delta time in seconds
        """
        pass

    @abstractmethod
    def render(self, screen: pygame.Surface) -> None:
        """
        Render the element.

        Args:
            screen: Pygame surface to draw on
        """
        pass

    def remove(self) -> None:
        """Remove this element from the physics world."""
        self._active = False
