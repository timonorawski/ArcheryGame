"""
Candy - the payload object that must reach the goal.
"""
from typing import Tuple, Optional
import math

import pygame
import pymunk

from games.SweetPhysics import config
from games.SweetPhysics.elements.base import Element
from games.SweetPhysics.physics.world import PhysicsWorld


class Candy(Element):
    """
    The candy/payload that the player guides to the goal.

    A circular physics body affected by gravity and collisions.
    """

    def __init__(
        self,
        world: PhysicsWorld,
        position: Tuple[float, float],
        radius: float = config.CANDY_RADIUS,
        mass: float = config.CANDY_MASS,
    ):
        """
        Initialize candy.

        Args:
            world: Physics world
            position: Initial position (x, y)
            radius: Candy radius in pixels
            mass: Candy mass
        """
        super().__init__(world)

        self._radius = radius
        self._initial_position = position

        # Create physics body
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self._body = pymunk.Body(mass, moment)
        self._body.position = position

        # Create shape
        self._shape = pymunk.Circle(self._body, radius)
        self._shape.elasticity = config.CANDY_ELASTICITY
        self._shape.friction = config.CANDY_FRICTION
        self._shape.collision_type = config.COLLISION_CANDY

        # Store reference to candy in shape for collision callbacks
        self._shape.candy = self

        # Add to world
        world.add_body(self._body)
        world.add_shape(self._shape)

        # State
        self._in_bubble = False
        self._reached_goal = False
        self._lost = False

        # Visual effects
        self._trail: list = []
        self._max_trail = 10

    @property
    def body(self) -> pymunk.Body:
        """Get the physics body."""
        return self._body

    @property
    def shape(self) -> pymunk.Shape:
        """Get the physics shape."""
        return self._shape

    @property
    def position(self) -> Tuple[float, float]:
        """Get current position."""
        return tuple(self._body.position)

    @property
    def velocity(self) -> Tuple[float, float]:
        """Get current velocity."""
        return tuple(self._body.velocity)

    @property
    def radius(self) -> float:
        """Get candy radius."""
        return self._radius

    @property
    def in_bubble(self) -> bool:
        """Whether candy is inside a bubble."""
        return self._in_bubble

    @in_bubble.setter
    def in_bubble(self, value: bool) -> None:
        self._in_bubble = value

    @property
    def reached_goal(self) -> bool:
        """Whether candy has reached the goal."""
        return self._reached_goal

    @reached_goal.setter
    def reached_goal(self, value: bool) -> None:
        self._reached_goal = value

    @property
    def lost(self) -> bool:
        """Whether candy has been lost (out of bounds, hit spikes, etc)."""
        return self._lost

    @lost.setter
    def lost(self, value: bool) -> None:
        self._lost = value

    def is_out_of_bounds(self, width: int, height: int, margin: int = config.BOUNDS_MARGIN) -> bool:
        """
        Check if candy is outside playable bounds.

        Args:
            width: Screen width
            height: Screen height
            margin: Extra margin outside screen

        Returns:
            True if candy is out of bounds
        """
        x, y = self.position
        return (
            x < -margin or
            x > width + margin or
            y > height + margin  # Only check bottom, not top
        )

    def update(self, dt: float) -> None:
        """Update candy state."""
        # Update trail
        pos = self.position
        self._trail.append(pos)
        if len(self._trail) > self._max_trail:
            self._trail.pop(0)

    def render(self, screen: pygame.Surface) -> None:
        """Render the candy."""
        if not self._active:
            return

        x, y = self.position
        x, y = int(x), int(y)

        # Draw trail
        if len(self._trail) > 1:
            for i, (tx, ty) in enumerate(self._trail[:-1]):
                alpha = int(100 * (i / len(self._trail)))
                trail_radius = int(self._radius * 0.3 * (i / len(self._trail)))
                if trail_radius > 0:
                    trail_surf = pygame.Surface((trail_radius * 2, trail_radius * 2), pygame.SRCALPHA)
                    pygame.draw.circle(
                        trail_surf,
                        (*config.CANDY_COLOR[:3], alpha),
                        (trail_radius, trail_radius),
                        trail_radius
                    )
                    screen.blit(trail_surf, (int(tx) - trail_radius, int(ty) - trail_radius))

        # Draw candy body
        pygame.draw.circle(screen, config.CANDY_COLOR, (x, y), int(self._radius))

        # Draw outline
        pygame.draw.circle(screen, config.CANDY_OUTLINE, (x, y), int(self._radius), 3)

        # Draw highlight (shine effect)
        highlight_offset = int(self._radius * 0.3)
        highlight_radius = int(self._radius * 0.25)
        pygame.draw.circle(
            screen,
            (255, 200, 220),
            (x - highlight_offset, y - highlight_offset),
            highlight_radius
        )

        # Draw swirl pattern
        angle = math.atan2(self._body.velocity.y, self._body.velocity.x + 0.001)
        for i in range(3):
            swirl_angle = angle + i * (2 * math.pi / 3)
            sx = x + int(self._radius * 0.4 * math.cos(swirl_angle))
            sy = y + int(self._radius * 0.4 * math.sin(swirl_angle))
            pygame.draw.circle(screen, config.CANDY_OUTLINE, (sx, sy), 3)

    def reset(self) -> None:
        """Reset candy to initial state."""
        self._body.position = self._initial_position
        self._body.velocity = (0, 0)
        self._body.angular_velocity = 0
        self._in_bubble = False
        self._reached_goal = False
        self._lost = False
        self._trail.clear()
        self._active = True

    def remove(self) -> None:
        """Remove candy from physics world."""
        super().remove()
        self._world.remove_shape(self._shape)
        self._world.remove_body(self._body)
