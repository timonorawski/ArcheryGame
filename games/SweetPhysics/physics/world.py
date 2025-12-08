"""
Physics world wrapper for Pymunk.

Handles the physics simulation and provides a clean interface for game elements.
"""
from typing import List, Optional, Tuple, Callable
import pymunk

from games.SweetPhysics import config


class PhysicsWorld:
    """
    Wrapper around Pymunk Space for Sweet Physics game.

    Manages physics simulation, collision detection, and element updates.
    """

    def __init__(
        self,
        gravity: Tuple[float, float] = config.GRAVITY,
        damping: float = config.AIR_RESISTANCE,
    ):
        """
        Initialize physics world.

        Args:
            gravity: Gravity vector (x, y) in pixels/sec^2
            damping: Global velocity damping (air resistance)
        """
        self._space = pymunk.Space()
        self._space.gravity = gravity
        self._space.damping = damping

        # Collision handlers
        self._collision_handlers: List[Tuple[int, int, Callable]] = []

        # Track bodies/shapes for removal
        self._bodies: List[pymunk.Body] = []
        self._shapes: List[pymunk.Shape] = []
        self._constraints: List[pymunk.Constraint] = []

    @property
    def space(self) -> pymunk.Space:
        """Get the underlying Pymunk space."""
        return self._space

    def add_body(self, body: pymunk.Body) -> None:
        """Add a body to the physics world."""
        self._space.add(body)
        self._bodies.append(body)

    def add_shape(self, shape: pymunk.Shape) -> None:
        """Add a shape to the physics world."""
        self._space.add(shape)
        self._shapes.append(shape)

    def add_constraint(self, constraint: pymunk.Constraint) -> None:
        """Add a constraint (joint) to the physics world."""
        self._space.add(constraint)
        self._constraints.append(constraint)

    def remove_body(self, body: pymunk.Body) -> None:
        """Remove a body from the physics world."""
        if body in self._bodies:
            self._space.remove(body)
            self._bodies.remove(body)

    def remove_shape(self, shape: pymunk.Shape) -> None:
        """Remove a shape from the physics world."""
        if shape in self._shapes:
            self._space.remove(shape)
            self._shapes.remove(shape)

    def remove_constraint(self, constraint: pymunk.Constraint) -> None:
        """Remove a constraint from the physics world."""
        if constraint in self._constraints:
            self._space.remove(constraint)
            self._constraints.remove(constraint)

    def add_collision_handler(
        self,
        type_a: int,
        type_b: int,
        begin: Optional[Callable] = None,
        separate: Optional[Callable] = None,
    ) -> None:
        """
        Add a collision handler between two collision types.

        Args:
            type_a: First collision type
            type_b: Second collision type
            begin: Called when collision begins
            separate: Called when objects separate
        """
        self._space.on_collision(
            collision_type_a=type_a,
            collision_type_b=type_b,
            begin=begin,
            separate=separate,
        )

    def update(self, dt: float, steps: int = config.PHYSICS_STEPS) -> None:
        """
        Step the physics simulation.

        Args:
            dt: Delta time in seconds
            steps: Number of substeps for stability
        """
        step_dt = dt / steps
        for _ in range(steps):
            self._space.step(step_dt)

    def create_static_segment(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        radius: float = 1.0,
        collision_type: int = config.COLLISION_WALL,
        elasticity: float = 0.5,
        friction: float = 0.8,
    ) -> pymunk.Segment:
        """
        Create a static wall segment.

        Args:
            start: Start point (x, y)
            end: End point (x, y)
            radius: Thickness of segment
            collision_type: Collision type for filtering
            elasticity: Bounciness
            friction: Surface friction

        Returns:
            The created segment shape
        """
        body = self._space.static_body
        segment = pymunk.Segment(body, start, end, radius)
        segment.collision_type = collision_type
        segment.elasticity = elasticity
        segment.friction = friction

        self._space.add(segment)
        self._shapes.append(segment)

        return segment

    def create_bounds(
        self,
        width: int,
        height: int,
        margin: int = config.BOUNDS_MARGIN,
    ) -> List[pymunk.Segment]:
        """
        Create boundary walls around the play area.

        Args:
            width: Screen width
            height: Screen height
            margin: Distance outside screen for bounds

        Returns:
            List of boundary segments
        """
        bounds = []

        # Left wall
        bounds.append(self.create_static_segment(
            (-margin, -margin),
            (-margin, height + margin),
        ))

        # Right wall
        bounds.append(self.create_static_segment(
            (width + margin, -margin),
            (width + margin, height + margin),
        ))

        # Bottom (loss zone - handled separately)
        # We don't create a bottom wall - candy falling below bounds = loss

        # Top
        bounds.append(self.create_static_segment(
            (-margin, -margin),
            (width + margin, -margin),
        ))

        return bounds

    def point_query(
        self,
        point: Tuple[float, float],
        max_distance: float,
        shape_filter: pymunk.ShapeFilter = pymunk.ShapeFilter(),
    ) -> List[pymunk.PointQueryInfo]:
        """
        Query shapes near a point.

        Args:
            point: Query point (x, y)
            max_distance: Maximum distance to search
            shape_filter: Filter for shape types

        Returns:
            List of query results
        """
        return self._space.point_query(point, max_distance, shape_filter)

    def segment_query(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        radius: float = 1.0,
        shape_filter: pymunk.ShapeFilter = pymunk.ShapeFilter(),
    ) -> List[pymunk.SegmentQueryInfo]:
        """
        Query shapes along a line segment.

        Args:
            start: Start point (x, y)
            end: End point (x, y)
            radius: Query radius
            shape_filter: Filter for shape types

        Returns:
            List of query results
        """
        return self._space.segment_query(start, end, radius, shape_filter)

    def clear(self) -> None:
        """Remove all bodies, shapes, and constraints."""
        # Remove constraints first
        for constraint in self._constraints[:]:
            self._space.remove(constraint)
        self._constraints.clear()

        # Remove shapes
        for shape in self._shapes[:]:
            self._space.remove(shape)
        self._shapes.clear()

        # Remove bodies (except static body)
        for body in self._bodies[:]:
            self._space.remove(body)
        self._bodies.clear()
