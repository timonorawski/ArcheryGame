"""
Goal zone - where the candy must reach to win.
"""
from typing import Tuple
import math

import pygame
import pymunk

from games.SweetPhysics import config
from games.SweetPhysics.elements.base import Element
from games.SweetPhysics.physics.world import PhysicsWorld


class Goal(Element):
    """
    The goal zone where candy must reach to complete the level.

    A sensor that detects when candy enters without affecting physics.
    """

    def __init__(
        self,
        world: PhysicsWorld,
        position: Tuple[float, float],
        radius: float = config.GOAL_RADIUS,
    ):
        """
        Initialize goal.

        Args:
            world: Physics world
            position: Center position (x, y)
            radius: Goal radius
        """
        super().__init__(world)

        self._position = position
        self._radius = radius

        # Create sensor shape (no collision response)
        self._body = world.space.static_body
        self._shape = pymunk.Circle(self._body, radius, position)
        self._shape.sensor = True  # Detects collision but doesn't respond
        self._shape.collision_type = config.COLLISION_GOAL

        world.add_shape(self._shape)

        # Visual effects
        self._pulse_phase = 0.0
        self._candy_inside = False

    @property
    def position(self) -> Tuple[float, float]:
        """Get goal position."""
        return self._position

    @property
    def radius(self) -> float:
        """Get goal radius."""
        return self._radius

    def contains_candy(self, candy_pos: Tuple[float, float], candy_radius: float) -> bool:
        """
        Check if candy is fully inside the goal.

        Args:
            candy_pos: Candy center position
            candy_radius: Candy radius

        Returns:
            True if candy center is within goal
        """
        dx = candy_pos[0] - self._position[0]
        dy = candy_pos[1] - self._position[1]
        dist = math.sqrt(dx * dx + dy * dy)

        # Candy center must be within goal
        return dist < self._radius - candy_radius * 0.5

    def update(self, dt: float) -> None:
        """Update goal animation."""
        self._pulse_phase += dt * config.GOAL_PULSE_SPEED

    def render(self, screen: pygame.Surface) -> None:
        """Render the goal."""
        if not self._active:
            return

        x, y = self._position
        x, y = int(x), int(y)

        # Pulsing effect
        pulse = 0.1 * math.sin(self._pulse_phase * 2 * math.pi)
        current_radius = int(self._radius * (1 + pulse))

        # Outer glow
        glow_radius = current_radius + 10
        glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        for r in range(glow_radius, current_radius, -2):
            alpha = int(30 * (1 - (r - current_radius) / 10))
            pygame.draw.circle(
                glow_surf,
                (*config.GOAL_COLOR, alpha),
                (glow_radius, glow_radius),
                r
            )
        screen.blit(glow_surf, (x - glow_radius, y - glow_radius))

        # Main circle (translucent)
        goal_surf = pygame.Surface((current_radius * 2, current_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            goal_surf,
            (*config.GOAL_COLOR, 100),
            (current_radius, current_radius),
            current_radius
        )
        screen.blit(goal_surf, (x - current_radius, y - current_radius))

        # Outline
        pygame.draw.circle(screen, config.GOAL_OUTLINE, (x, y), current_radius, 3)

        # Inner pattern (concentric rings)
        for i in range(1, 4):
            ring_radius = int(current_radius * i / 4)
            pygame.draw.circle(
                screen,
                (*config.GOAL_OUTLINE, 100),
                (x, y),
                ring_radius,
                1
            )

        # Center marker
        pygame.draw.circle(screen, config.GOAL_OUTLINE, (x, y), 5)

    def remove(self) -> None:
        """Remove goal from physics world."""
        super().remove()
        self._world.remove_shape(self._shape)
