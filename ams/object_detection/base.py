"""
Base classes for object detection.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np
from models import Point2D


@dataclass
class DetectedObject:
    """Represents a detected object in the camera frame.

    Attributes:
        position: Center position (x, y) in camera coordinates
        velocity: Velocity vector (dx/dt, dy/dt) in pixels/second
        area: Area of the detected blob in pixels
        bounding_box: (x, y, width, height) of bounding box
        confidence: Detection confidence (0.0-1.0)
        timestamp: Time of detection
    """
    position: Point2D
    velocity: Point2D  # Using Point2D as 2D vector
    area: float
    bounding_box: Tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float
    timestamp: float


@dataclass
class ImpactEvent:
    """Represents a detected impact event.

    Attributes:
        position: Impact position in camera coordinates
        velocity_before: Velocity before impact (pixels/sec)
        timestamp: Time of impact
        stationary_duration: How long object has been stationary (seconds)
    """
    position: Point2D
    velocity_before: Point2D
    timestamp: float
    stationary_duration: float


class ObjectDetector(ABC):
    """Abstract base class for object detection algorithms.

    Subclasses implement specific detection methods (color blob, shape, etc.)
    All detectors must provide a consistent interface for the backend.
    """

    @abstractmethod
    def detect(self, frame: np.ndarray, timestamp: float) -> List[DetectedObject]:
        """Detect objects in the given frame.

        Args:
            frame: BGR image from camera
            timestamp: Current timestamp for velocity calculation

        Returns:
            List of detected objects with positions and velocities
        """
        pass

    @abstractmethod
    def get_debug_frame(self) -> Optional[np.ndarray]:
        """Get debug visualization frame.

        Returns:
            Frame with detection visualization overlays, or None
        """
        pass

    @abstractmethod
    def set_debug_mode(self, enabled: bool) -> None:
        """Enable/disable debug visualization.

        Args:
            enabled: Whether to generate debug frames
        """
        pass

    @abstractmethod
    def configure(self, **kwargs) -> None:
        """Update detector configuration dynamically.

        Args:
            **kwargs: Configuration parameters specific to detector type
        """
        pass
