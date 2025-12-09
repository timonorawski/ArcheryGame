"""
Browser-compatible primitive types using dataclasses instead of Pydantic.

These classes provide the same API as the Pydantic versions but work in WASM.
"""
from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class Point2D:
    """Immutable 2D point/vector."""
    x: float
    y: float

    def __str__(self) -> str:
        return f"Point2D(x={self.x:.2f}, y={self.y:.2f})"


# Alias for backward compatibility
Vector2D = Point2D


@dataclass(frozen=True)
class Resolution:
    """Display resolution."""
    width: int
    height: int

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    def __str__(self) -> str:
        return f"Resolution({self.width}x{self.height})"


@dataclass(frozen=True)
class Color:
    """RGBA color."""
    r: int
    g: int
    b: int
    a: int = 255

    @property
    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.r, self.g, self.b, self.a)

    @property
    def as_rgb_tuple(self) -> Tuple[int, int, int]:
        return (self.r, self.g, self.b)

    def __str__(self) -> str:
        return f"Color(r={self.r}, g={self.g}, b={self.b}, a={self.a})"


@dataclass(frozen=True)
class Rectangle:
    """Rectangle defined by position and dimensions."""
    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point2D:
        return Point2D(
            x=self.x + self.width / 2,
            y=self.y + self.height / 2
        )

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def contains_point(self, point: Point2D) -> bool:
        return (self.left <= point.x <= self.right and
                self.top <= point.y <= self.bottom)

    def intersects(self, other: 'Rectangle') -> bool:
        return not (self.right < other.left or
                   self.left > other.right or
                   self.bottom < other.top or
                   self.top > other.bottom)

    def __str__(self) -> str:
        return f"Rectangle(x={self.x:.2f}, y={self.y:.2f}, w={self.width:.2f}, h={self.height:.2f})"
