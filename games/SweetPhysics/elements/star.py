"""
Star collectible - bonus points when candy passes through.
"""
from typing import Tuple
import math

import pygame
import pymunk

from games.SweetPhysics import config
from games.SweetPhysics.elements.base import Element
from games.SweetPhysics.physics.world import PhysicsWorld


class Star(Element):
    """
    Collectible star that candy can pick up for bonus points.

    A sensor that detects when candy enters.
    """

    def __init__(
        self,
        world: PhysicsWorld,
        position: Tuple[float, float],
        radius: float = config.STAR_RADIUS,
    ):
        """
        Initialize star.

        Args:
            world: Physics world
            position: Center position (x, y)
            radius: Star radius
        """
        super().__init__(world)

        self._position = position
        self._radius = radius

        # Create sensor shape
        self._body = world.space.static_body
        self._shape = pymunk.Circle(self._body, radius, position)
        self._shape.sensor = True
        self._shape.collision_type = config.COLLISION_STAR

        # Store reference to star for collision callbacks
        self._shape.star = self

        world.add_shape(self._shape)

        # State
        self._collected = False

        # Visual effects
        self._rotation = 0.0
        self._sparkle_phase = 0.0

    @property
    def position(self) -> Tuple[float, float]:
        """Get star position."""
        return self._position

    @property
    def collected(self) -> bool:
        """Whether star has been collected."""
        return self._collected

    def collect(self) -> None:
        """Mark star as collected."""
        self._collected = True

    def contains_point(self, x: float, y: float) -> bool:
        """Check if point is inside star."""
        dx = x - self._position[0]
        dy = y - self._position[1]
        return math.sqrt(dx * dx + dy * dy) < self._radius

    def update(self, dt: float) -> None:
        """Update star animation."""
        if not self._collected:
            self._rotation += dt * 2.0  # Rotate
            self._sparkle_phase += dt * 3.0

    def render(self, screen: pygame.Surface) -> None:
        """Render the star."""
        if not self._active:
            return

        x, y = self._position
        x, y = int(x), int(y)

        if self._collected:
            # Render faded/ghosted star
            self._render_star_shape(screen, x, y, alpha=50)
        else:
            # Render sparkle effect
            self._render_sparkles(screen, x, y)

            # Render full star
            self._render_star_shape(screen, x, y, alpha=255)

    def _render_star_shape(self, screen: pygame.Surface, x: int, y: int, alpha: int = 255) -> None:
        """Render the star shape."""
        # Create star polygon
        points = []
        num_points = 5
        outer_radius = self._radius
        inner_radius = self._radius * 0.4

        for i in range(num_points * 2):
            angle = self._rotation + i * math.pi / num_points - math.pi / 2
            radius = outer_radius if i % 2 == 0 else inner_radius
            px = x + radius * math.cos(angle)
            py = y + radius * math.sin(angle)
            points.append((px, py))

        if alpha < 255:
            # Draw with transparency
            star_surf = pygame.Surface((int(outer_radius * 2.5), int(outer_radius * 2.5)), pygame.SRCALPHA)
            offset_points = [(p[0] - x + outer_radius * 1.25, p[1] - y + outer_radius * 1.25) for p in points]
            pygame.draw.polygon(star_surf, (*config.STAR_COLOR, alpha), offset_points)
            pygame.draw.polygon(star_surf, (*config.STAR_OUTLINE, alpha), offset_points, 2)
            screen.blit(star_surf, (x - outer_radius * 1.25, y - outer_radius * 1.25))
        else:
            # Draw normally
            pygame.draw.polygon(screen, config.STAR_COLOR, points)
            pygame.draw.polygon(screen, config.STAR_OUTLINE, points, 2)

            # Highlight
            highlight_points = []
            for i in range(num_points * 2):
                angle = self._rotation + i * math.pi / num_points - math.pi / 2
                radius = (outer_radius * 0.6) if i % 2 == 0 else (inner_radius * 0.6)
                px = x + radius * math.cos(angle) - 2
                py = y + radius * math.sin(angle) - 2
                highlight_points.append((px, py))
            pygame.draw.polygon(screen, (255, 240, 150), highlight_points)

    def _render_sparkles(self, screen: pygame.Surface, x: int, y: int) -> None:
        """Render sparkle effects around the star."""
        num_sparkles = 4
        sparkle_dist = self._radius * 1.5

        for i in range(num_sparkles):
            angle = self._sparkle_phase + i * (2 * math.pi / num_sparkles)
            sparkle_alpha = int(128 + 127 * math.sin(self._sparkle_phase * 2 + i))

            sx = x + int(sparkle_dist * math.cos(angle))
            sy = y + int(sparkle_dist * math.sin(angle))

            # Small sparkle
            sparkle_surf = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(sparkle_surf, (*config.STAR_COLOR, sparkle_alpha), (4, 4), 3)
            screen.blit(sparkle_surf, (sx - 4, sy - 4))

    def remove(self) -> None:
        """Remove star from physics world."""
        super().remove()
        self._world.remove_shape(self._shape)
