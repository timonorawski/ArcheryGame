"""
Object detection package for AMS.

Provides flexible object detection with pluggable detector implementations.
"""

from .base import ObjectDetector, DetectedObject, ImpactEvent
from .color_blob import ColorBlobDetector
from .config import ColorBlobConfig, DetectorType, ImpactMode, ImpactDetectionConfig

__all__ = [
    "ObjectDetector",
    "DetectedObject",
    "ImpactEvent",
    "ColorBlobDetector",
    "ColorBlobConfig",
    "DetectorType",
    "ImpactMode",
    "ImpactDetectionConfig",
]
