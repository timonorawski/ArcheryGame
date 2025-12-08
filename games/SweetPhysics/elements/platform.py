"""
Platform element - static collision surface.
"""
from typing import Tuple

import pygame
import pymunk

from games.SweetPhysics import config
from games.SweetPhysics.elements.base import Element
from games.SweetPhysics.physics.world import PhysicsWorld


class Platform(Element):
    """
    A static platform that candy can collide with.
    """

    def __init__(
        self,
        world: PhysicsWorld,
        start: Tuple[float, float],
        end: Tuple[float, float],
        thickness: float = 10,
        elasticity: float = 0.3,
        friction: float = 0.8,
    ):
        """
        Initialize platform.

        Args:
            world: Physics world
            start: Start point (x, y)
            end: End point (x, y)
            thickness: Platform thickness
            elasticity: Bounciness
            friction: Surface friction
        """
        super().__init__(world)

        self._start = start
        self._end = end
        self._thickness = thickness

        # Create segment shape
        self._shape = world.create_static_segment(
            start, end,
            radius=thickness / 2,
            collision_type=config.COLLISION_WALL,
            elasticity=elasticity,
            friction=friction,
        )

    @property
    def start(self) -> Tuple[float, float]:
        """Get start point."""
        return self._start

    @property
    def end(self) -> Tuple[float, float]:
        """Get end point."""
        return self._end

    def render(self, screen: pygame.Surface) -> None:
        """Render the platform."""
        if not self._active:
            return

        x1, y1 = self._start
        x2, y2 = self._end

        # Draw thick line
        pygame.draw.line(
            screen,
            config.PLATFORM_COLOR,
            (int(x1), int(y1)),
            (int(x2), int(y2)),
            int(self._thickness)
        )

        # Draw outline
        pygame.draw.line(
            screen,
            config.PLATFORM_OUTLINE,
            (int(x1), int(y1)),
            (int(x2), int(y2)),
            int(self._thickness) + 2
        )
        pygame.draw.line(
            screen,
            config.PLATFORM_COLOR,
            (int(x1), int(y1)),
            (int(x2), int(y2)),
            int(self._thickness) - 2
        )

        # End caps
        pygame.draw.circle(screen, config.PLATFORM_COLOR, (int(x1), int(y1)), int(self._thickness / 2))
        pygame.draw.circle(screen, config.PLATFORM_COLOR, (int(x2), int(y2)), int(self._thickness / 2))

    def remove(self) -> None:
        """Remove platform from physics world."""
        super().remove()
        self._world.remove_shape(self._shape)
