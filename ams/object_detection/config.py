"""
Configuration models for object detection.
"""

from enum import Enum
from typing import Tuple
from pydantic import BaseModel, Field


class DetectorType(str, Enum):
    """Object detector algorithm types."""
    COLOR_BLOB = "color_blob"
    SHAPE_DETECTION = "shape_detection"
    TEMPLATE_MATCHING = "template_matching"
    DEEP_LEARNING = "deep_learning"


class ColorBlobConfig(BaseModel):
    """Configuration for color blob detector.

    Uses HSV color space for robust color detection under varying lighting.
    """

    # HSV color range
    hue_min: int = Field(default=0, ge=0, le=179, description="Minimum hue value (0-179)")
    hue_max: int = Field(default=10, ge=0, le=179, description="Maximum hue value (0-179)")
    saturation_min: int = Field(default=100, ge=0, le=255, description="Minimum saturation (0-255)")
    saturation_max: int = Field(default=255, ge=0, le=255, description="Maximum saturation (0-255)")
    value_min: int = Field(default=100, ge=0, le=255, description="Minimum brightness value (0-255)")
    value_max: int = Field(default=255, ge=0, le=255, description="Maximum brightness value (0-255)")

    # Morphological operations
    erode_iterations: int = Field(default=2, ge=0, le=10, description="Erosion iterations to remove noise")
    dilate_iterations: int = Field(default=2, ge=0, le=10, description="Dilation iterations to close gaps")

    # Blob detection
    min_area: int = Field(default=50, ge=1, description="Minimum blob area in pixels")
    max_area: int = Field(default=5000, ge=1, description="Maximum blob area in pixels")

    # Impact detection
    impact_velocity_threshold: float = Field(
        default=10.0,
        ge=0.0,
        description="Velocity threshold (pixels/sec) below which object is considered stopped"
    )
    impact_stationary_duration: float = Field(
        default=0.1,
        ge=0.0,
        description="Duration (seconds) object must be stationary to register impact"
    )

    def get_hsv_lower(self) -> Tuple[int, int, int]:
        """Get lower HSV bound as tuple."""
        return (self.hue_min, self.saturation_min, self.value_min)

    def get_hsv_upper(self) -> Tuple[int, int, int]:
        """Get upper HSV bound as tuple."""
        return (self.hue_max, self.saturation_max, self.value_max)


class ImpactDetectionConfig(BaseModel):
    """Configuration for impact detection."""

    velocity_threshold: float = Field(
        default=10.0,
        ge=0.0,
        description="Velocity threshold (pixels/sec) for considering object stopped"
    )
    stationary_duration: float = Field(
        default=0.1,
        ge=0.0,
        description="Duration (seconds) object must be stationary"
    )
    max_tracking_gap: float = Field(
        default=0.5,
        ge=0.0,
        description="Maximum time gap (seconds) before losing track of object"
    )
