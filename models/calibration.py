"""
Calibration data models for the projection targeting system.

These models handle geometric calibration, ArUco marker detection,
and homography transformations between camera and projector coordinate systems.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal, Tuple
from datetime import datetime
import numpy as np
from pathlib import Path

from .primitives import Point2D, Resolution


class HomographyMatrix(BaseModel):
    """
    3x3 homography transformation matrix.
    Stored as flat list for JSON serialization.

    Used to transform coordinates between camera space and projector space.
    """
    matrix: List[List[float]] = Field(..., min_length=3, max_length=3)

    @field_validator('matrix')
    @classmethod
    def validate_matrix_shape(cls, v):
        if len(v) != 3 or any(len(row) != 3 for row in v):
            raise ValueError("Matrix must be 3x3")
        return v

    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array for OpenCV operations."""
        return np.array(self.matrix, dtype=np.float64)

    @classmethod
    def from_numpy(cls, arr: np.ndarray) -> 'HomographyMatrix':
        """Create from numpy array."""
        if arr.shape != (3, 3):
            raise ValueError(f"Expected 3x3 array, got {arr.shape}")
        return cls(matrix=arr.tolist())


class MarkerDetection(BaseModel):
    """Single ArUco marker detection result."""
    marker_id: int
    corners: List[Point2D] = Field(..., min_length=4, max_length=4)
    center: Point2D


class CalibrationQuality(BaseModel):
    """Metrics describing calibration quality."""
    reprojection_error_rms: float = Field(..., ge=0)
    reprojection_error_max: float = Field(..., ge=0)
    num_inliers: int = Field(..., ge=0)
    num_total_points: int = Field(..., ge=0)
    inlier_ratio: float = Field(..., ge=0, le=1)

    # Computed quality score
    quality_score: Optional[float] = Field(default=None, ge=0, le=1)

    @property
    def is_acceptable(self) -> bool:
        """Check if calibration meets quality thresholds."""
        return (
            self.reprojection_error_rms < 3.0 and
            self.inlier_ratio > 0.8
        )


class ScreenBounds(BaseModel):
    """
    Camera-space polygon representing the projected screen area.

    The camera typically sees more than just the projection surface.
    This polygon defines the corners of the projected screen in camera
    pixel coordinates, allowing detection to filter out hits outside
    the active game area.
    """
    # Four corners in camera pixel coordinates (clockwise from top-left)
    top_left: Point2D
    top_right: Point2D
    bottom_right: Point2D
    bottom_left: Point2D

    def to_numpy_polygon(self) -> 'np.ndarray':
        """Convert to numpy polygon for cv2.pointPolygonTest."""
        import numpy as np
        return np.array([
            [self.top_left.x, self.top_left.y],
            [self.top_right.x, self.top_right.y],
            [self.bottom_right.x, self.bottom_right.y],
            [self.bottom_left.x, self.bottom_left.y],
        ], dtype=np.float32)

    def contains_point(self, x: float, y: float) -> bool:
        """Check if a camera-space point is within the screen bounds."""
        import cv2
        polygon = self.to_numpy_polygon()
        result = cv2.pointPolygonTest(polygon, (x, y), False)
        return result >= 0  # >= 0 means inside or on edge


class CalibrationData(BaseModel):
    """
    Complete calibration data for persistence.
    This is the main data structure saved/loaded from disk.
    """
    version: str = "1.1"  # Bumped for screen_bounds addition
    calibration_time: datetime = Field(default_factory=datetime.now)
    # Alias for backward compatibility
    timestamp: Optional[datetime] = None

    projector_resolution: Resolution
    camera_resolution: Resolution
    homography_camera_to_projector: HomographyMatrix
    quality: CalibrationQuality
    detection_method: Literal["aruco_4x4", "aruco_5x5", "checkerboard"] = "aruco_4x4"
    marker_count: int = Field(default=0, ge=0)
    # Alias for backward compatibility
    num_calibration_points: Optional[int] = None

    # Screen bounds in camera space (for filtering out-of-bounds detections)
    screen_bounds: Optional[ScreenBounds] = None

    # Optional metadata
    notes: Optional[str] = None
    hardware_config: Optional[dict] = None

    def model_post_init(self, __context):
        """Handle backward compatibility aliases."""
        # If timestamp not set, use calibration_time
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', self.calibration_time)
        # If num_calibration_points not set, use marker_count
        if self.num_calibration_points is None:
            object.__setattr__(self, 'num_calibration_points', self.marker_count)

    def save(self, filepath: str):
        """Save calibration to JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, filepath: str) -> 'CalibrationData':
        """Load calibration from JSON file."""
        with open(filepath, 'r') as f:
            return cls.model_validate_json(f.read())


class CalibrationConfig(BaseModel):
    """Configuration parameters for calibration process."""
    pattern_type: Literal["aruco"] = "aruco"
    aruco_dict: str = "DICT_4X4_50"
    grid_size: Tuple[int, int] = (4, 4)
    margin_percent: float = Field(default=0.1, ge=0, le=0.5)
    min_markers_required: int = Field(default=12, ge=4)

    # Homography parameters
    ransac_threshold: float = Field(default=5.0, gt=0)
    max_reprojection_error: float = Field(default=3.0, gt=0)

    # Validation
    corner_test_enabled: bool = True
    interactive_verification: bool = False

    # Persistence
    auto_save: bool = True
    calibration_dir: str = "./calibration_data"
    keep_history: int = Field(default=5, ge=1)

    def save(self, filepath: str):
        """Save configuration to JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, filepath: str) -> 'CalibrationConfig':
        """Load configuration from JSON file."""
        with open(filepath, 'r') as f:
            return cls.model_validate_json(f.read())
