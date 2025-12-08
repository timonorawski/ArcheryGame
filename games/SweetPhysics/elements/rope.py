"""
Rope element - can be cut by player to release attached objects.
"""
from typing import Tuple, Optional, List
import math

import pygame
import pymunk

from games.SweetPhysics import config
from games.SweetPhysics.elements.base import Element
from games.SweetPhysics.physics.world import PhysicsWorld


class RopeSegment:
    """A single segment of a rope."""

    def __init__(
        self,
        body: pymunk.Body,
        shape: pymunk.Segment,
        joint_to_prev: Optional[pymunk.Constraint],
    ):
        self.body = body
        self.shape = shape
        self.joint_to_prev = joint_to_prev


class Rope(Element):
    """
    A rope that can be cut by the player.

    Implemented as a chain of physics segments connected by pivot joints.
    """

    def __init__(
        self,
        world: PhysicsWorld,
        anchor: Tuple[float, float],
        attach_body: Optional[pymunk.Body] = None,
        length: float = 150,
        segments: int = 8,
    ):
        """
        Initialize rope.

        Args:
            world: Physics world
            anchor: Fixed anchor point (x, y)
            attach_body: Body to attach end to (e.g., candy), or None for free end
            length: Total rope length in pixels
            segments: Number of segments
        """
        super().__init__(world)

        self._anchor = anchor
        self._attach_body = attach_body
        self._total_length = length
        self._num_segments = segments
        self._segment_length = length / segments

        self._segments: List[RopeSegment] = []
        self._cut = False
        self._cut_index: Optional[int] = None

        # Create rope segments
        self._create_rope()

    @property
    def targetable(self) -> bool:
        """Ropes can be targeted (cut)."""
        return True

    @property
    def is_cut(self) -> bool:
        """Whether the rope has been cut."""
        return self._cut

    def _create_rope(self) -> None:
        """Create the rope physics bodies and joints."""
        space = self._world.space
        anchor_x, anchor_y = self._anchor

        prev_body = space.static_body
        prev_pos = self._anchor

        for i in range(self._num_segments):
            # Calculate segment end position (hanging straight down initially)
            seg_end_y = anchor_y + (i + 1) * self._segment_length

            # Create segment body
            mass = config.ROPE_SEGMENT_MASS
            moment = pymunk.moment_for_segment(mass, (0, 0), (0, self._segment_length), 2)
            body = pymunk.Body(mass, moment)
            body.position = (anchor_x, anchor_y + i * self._segment_length + self._segment_length / 2)

            # Create segment shape (for collision/rendering reference)
            shape = pymunk.Segment(
                body,
                (0, -self._segment_length / 2),
                (0, self._segment_length / 2),
                2
            )
            shape.collision_type = config.COLLISION_WALL
            shape.filter = pymunk.ShapeFilter(categories=0)  # No collision

            self._world.add_body(body)
            self._world.add_shape(shape)

            # Create joint to previous body
            if i == 0:
                # First segment connects to static anchor
                joint = pymunk.PivotJoint(
                    prev_body,
                    body,
                    self._anchor,
                    (0, -self._segment_length / 2)
                )
            else:
                # Connect to previous segment
                joint = pymunk.PivotJoint(
                    prev_body,
                    body,
                    (0, self._segment_length / 2),
                    (0, -self._segment_length / 2)
                )

            self._world.add_constraint(joint)

            self._segments.append(RopeSegment(body, shape, joint))
            prev_body = body

        # Attach end to target body if provided
        if self._attach_body is not None:
            last_segment = self._segments[-1]
            attach_joint = pymunk.PivotJoint(
                last_segment.body,
                self._attach_body,
                (0, self._segment_length / 2),
                (0, 0)
            )
            self._world.add_constraint(attach_joint)
            self._attach_joint = attach_joint
        else:
            self._attach_joint = None

    def get_segment_positions(self) -> List[Tuple[float, float]]:
        """
        Get the world positions of all segment endpoints.

        Returns:
            List of (x, y) positions from anchor to end
        """
        positions = [self._anchor]

        for seg in self._segments:
            if not self._cut or self._segments.index(seg) < self._cut_index:
                # Get world position of segment end
                local_end = (0, self._segment_length / 2)
                world_end = seg.body.local_to_world(local_end)
                positions.append((world_end.x, world_end.y))

        return positions

    def check_hit(self, x: float, y: float, radius: float = config.ROPE_HIT_RADIUS) -> bool:
        """Check if a hit intersects any rope segment."""
        if self._cut:
            return False

        positions = self.get_segment_positions()

        for i in range(len(positions) - 1):
            p1 = positions[i]
            p2 = positions[i + 1]

            # Point-to-segment distance
            dist = self._point_to_segment_distance(x, y, p1[0], p1[1], p2[0], p2[1])
            if dist < radius:
                return True

        return False

    def _point_to_segment_distance(
        self,
        px: float, py: float,
        x1: float, y1: float,
        x2: float, y2: float
    ) -> float:
        """Calculate distance from point to line segment."""
        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx * dx + dy * dy

        if length_sq == 0:
            return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)

        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy

        return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)

    def on_hit(self, x: float, y: float) -> bool:
        """Handle being hit - cut the rope at this position."""
        if self._cut:
            return False

        positions = self.get_segment_positions()

        for i in range(len(positions) - 1):
            p1 = positions[i]
            p2 = positions[i + 1]

            dist = self._point_to_segment_distance(x, y, p1[0], p1[1], p2[0], p2[1])
            if dist < config.ROPE_HIT_RADIUS:
                self._cut_at_segment(i)
                return True

        return False

    def _cut_at_segment(self, segment_index: int) -> None:
        """Cut the rope at the specified segment."""
        self._cut = True
        self._cut_index = segment_index

        # Remove joints from cut point onwards
        for i in range(segment_index, len(self._segments)):
            seg = self._segments[i]
            if seg.joint_to_prev is not None:
                self._world.remove_constraint(seg.joint_to_prev)
                seg.joint_to_prev = None

        # Remove attachment joint
        if self._attach_joint is not None:
            self._world.remove_constraint(self._attach_joint)
            self._attach_joint = None

        # Remove segments below cut (they fall away)
        for i in range(segment_index, len(self._segments)):
            seg = self._segments[i]
            self._world.remove_shape(seg.shape)
            self._world.remove_body(seg.body)

    def render(self, screen: pygame.Surface) -> None:
        """Render the rope."""
        if not self._active:
            return

        positions = self.get_segment_positions()

        if len(positions) < 2:
            return

        # Draw rope as thick line segments
        for i in range(len(positions) - 1):
            p1 = positions[i]
            p2 = positions[i + 1]

            pygame.draw.line(
                screen,
                config.ROPE_COLOR,
                (int(p1[0]), int(p1[1])),
                (int(p2[0]), int(p2[1])),
                config.ROPE_WIDTH
            )

        # Draw anchor point
        ax, ay = self._anchor
        pygame.draw.circle(screen, (100, 70, 40), (int(ax), int(ay)), 8)
        pygame.draw.circle(screen, (60, 40, 20), (int(ax), int(ay)), 8, 2)

        # Draw attachment point if rope is intact
        if not self._cut and len(positions) > 1:
            ex, ey = positions[-1]
            pygame.draw.circle(screen, config.ROPE_COLOR, (int(ex), int(ey)), 4)

    def remove(self) -> None:
        """Remove rope from physics world."""
        super().remove()

        # Remove attachment joint
        if self._attach_joint is not None:
            self._world.remove_constraint(self._attach_joint)

        # Remove all segments
        for seg in self._segments:
            if seg.joint_to_prev is not None:
                self._world.remove_constraint(seg.joint_to_prev)
            self._world.remove_shape(seg.shape)
            self._world.remove_body(seg.body)

        self._segments.clear()
