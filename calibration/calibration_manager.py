"""
Calibration Manager - main interface for the calibration system.

Manages calibration data and coordinate transformations.
Provides clean API for game engine integration.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional
from datetime import datetime

from models import (
    CalibrationData,
    CalibrationConfig,
    CalibrationQuality,
    Point2D,
    Resolution,
    HomographyMatrix,
    ScreenBounds,
)
from calibration.pattern_generator import ArucoPatternGenerator
from calibration.pattern_detector import ArucoPatternDetector
from calibration.homography import (
    compute_homography,
    compute_inverse_homography,
    apply_homography_single
)


class CalibrationManager:
    """
    Manages calibration data and coordinate transformations.
    Thread-safe for multi-process use.
    """

    def __init__(
        self,
        config: CalibrationConfig,
        calibration_file: Optional[str] = None
    ):
        """
        Initialize calibration manager.

        Args:
            config: Configuration parameters
            calibration_file: Optional path to existing calibration JSON
        """
        self.config = config
        self._calibration: Optional[CalibrationData] = None
        self._H_cam_to_proj: Optional[np.ndarray] = None  # Cached numpy matrix
        self._H_proj_to_cam: Optional[np.ndarray] = None  # Cached inverse

        if calibration_file:
            self.load_calibration(calibration_file)

    def is_calibrated(self) -> bool:
        """Check if valid calibration exists."""
        return self._calibration is not None

    def load_calibration(self, filepath: str) -> None:
        """
        Load calibration from file.

        Args:
            filepath: Path to calibration JSON file

        Raises:
            FileNotFoundError: If file doesn't exist
            ValidationError: If JSON is invalid
        """
        self._calibration = CalibrationData.load(filepath)
        self._H_cam_to_proj = self._calibration.homography_camera_to_projector.to_numpy()
        self._H_proj_to_cam = np.linalg.inv(self._H_cam_to_proj)

        print(f"Loaded calibration from {filepath}")
        print(f"  Quality: RMS error = {self._calibration.quality.reprojection_error_rms:.2f}px")
        print(f"  Acceptable: {self._calibration.quality.is_acceptable}")

        # Compute screen bounds if not present in loaded data
        # (for backward compatibility with older calibration files)
        if self._calibration.screen_bounds is None:
            screen_bounds = self._compute_screen_bounds(self._calibration.projector_resolution)
            # Update the calibration data with computed bounds
            # Note: Using object.__setattr__ since Pydantic models are frozen by default
            object.__setattr__(self._calibration, 'screen_bounds', screen_bounds)
            print(f"  Screen bounds: computed from homography")
        else:
            print(f"  Screen bounds: loaded from file")

    def camera_to_game(self, camera_point: Point2D) -> Point2D:
        """
        Transform point from camera space to game space (normalized).

        Args:
            camera_point: Point in camera pixel coordinates

        Returns:
            Point in normalized game coordinates [0, 1]

        Raises:
            RuntimeError: If not calibrated
        """
        if not self.is_calibrated():
            raise RuntimeError("No calibration loaded. Run calibrate() first.")

        # Transform camera → projector
        cam_pt = np.array([[camera_point.x, camera_point.y]], dtype=np.float32)
        proj_pt = cv2.perspectiveTransform(
            cam_pt.reshape(-1, 1, 2),
            self._H_cam_to_proj
        )[0][0]

        # Normalize to game space [0, 1]
        game_x = proj_pt[0] / self._calibration.projector_resolution.width
        game_y = proj_pt[1] / self._calibration.projector_resolution.height

        return Point2D(x=game_x, y=game_y)

    def game_to_projector(self, game_point: Point2D) -> Point2D:
        """
        Transform point from game space to projector space.

        Args:
            game_point: Point in normalized coordinates [0, 1]

        Returns:
            Point in projector pixel coordinates

        Raises:
            RuntimeError: If not calibrated
        """
        if not self.is_calibrated():
            raise RuntimeError("No calibration loaded. Run calibrate() first.")

        # Simple scaling from normalized to projector pixels
        proj_x = game_point.x * self._calibration.projector_resolution.width
        proj_y = game_point.y * self._calibration.projector_resolution.height

        return Point2D(x=proj_x, y=proj_y)

    def projector_to_camera(self, projector_point: Point2D) -> Point2D:
        """
        Transform point from projector space to camera space.

        Useful for projected pattern differencing detection.

        Args:
            projector_point: Point in projector pixel coordinates

        Returns:
            Point in camera pixel coordinates

        Raises:
            RuntimeError: If not calibrated
        """
        if not self.is_calibrated():
            raise RuntimeError("No calibration loaded. Run calibrate() first.")

        # Transform projector → camera (using inverse homography)
        proj_pt = np.array([[projector_point.x, projector_point.y]], dtype=np.float32)
        cam_pt = cv2.perspectiveTransform(
            proj_pt.reshape(-1, 1, 2),
            self._H_proj_to_cam
        )[0][0]

        return Point2D(x=cam_pt[0], y=cam_pt[1])

    def is_within_screen_bounds(self, camera_point: Point2D) -> bool:
        """
        Check if a camera-space point is within the projected screen area.

        The camera typically sees more than just the projection surface.
        This method filters out detections that fall outside the active
        game area (outside the projected screen).

        Args:
            camera_point: Point in camera pixel coordinates

        Returns:
            True if point is within the projected screen bounds,
            False if outside or if no bounds are available

        Note:
            Returns True if calibration has no screen_bounds (permissive fallback)
        """
        if not self.is_calibrated():
            return True  # No calibration = no filtering

        if self._calibration.screen_bounds is None:
            return True  # No bounds defined = no filtering

        return self._calibration.screen_bounds.contains_point(
            camera_point.x, camera_point.y
        )

    def get_screen_bounds(self) -> Optional[ScreenBounds]:
        """
        Get the camera-space polygon of the projected screen.

        Returns:
            ScreenBounds object, or None if not calibrated or no bounds
        """
        if not self.is_calibrated():
            return None
        return self._calibration.screen_bounds

    def get_camera_geometry(self) -> Optional[dict]:
        """
        Get camera viewing geometry for impact point estimation.

        Used by STUCK mode to determine which edge of a projectile
        blob is the actual impact point (tip vs tail).

        Returns:
            Dictionary with:
                - camera_center_x: Camera optical center X in pixels
                - camera_center_y: Camera optical center Y in pixels
            Or None if not calibrated.
        """
        if not self.is_calibrated():
            return None

        # Camera optical center is typically the image center
        cam_center_x = self._calibration.camera_resolution.width / 2
        cam_center_y = self._calibration.camera_resolution.height / 2

        return {
            'camera_center_x': cam_center_x,
            'camera_center_y': cam_center_y,
        }

    def _compute_screen_bounds(self, projector_resolution: Resolution) -> ScreenBounds:
        """
        Compute the camera-space corners of the projected screen.

        Projects the four corners of the projector resolution back to
        camera space to define the active detection area.

        Args:
            projector_resolution: The projector's resolution

        Returns:
            ScreenBounds with the four corners in camera pixel coordinates
        """
        w = projector_resolution.width
        h = projector_resolution.height

        # Projector corners (clockwise from top-left)
        corners_proj = [
            Point2D(x=0, y=0),      # top-left
            Point2D(x=w, y=0),      # top-right
            Point2D(x=w, y=h),      # bottom-right
            Point2D(x=0, y=h),      # bottom-left
        ]

        # Transform each corner to camera space
        corners_cam = [self.projector_to_camera(p) for p in corners_proj]

        return ScreenBounds(
            top_left=corners_cam[0],
            top_right=corners_cam[1],
            bottom_right=corners_cam[2],
            bottom_left=corners_cam[3],
        )

    def get_calibration_quality(self) -> CalibrationQuality:
        """
        Get quality metrics for current calibration.

        Returns:
            CalibrationQuality object

        Raises:
            RuntimeError: If not calibrated
        """
        if not self.is_calibrated():
            raise RuntimeError("No calibration loaded.")
        return self._calibration.quality

    def get_calibration_data(self) -> CalibrationData:
        """
        Get complete calibration data.

        Returns:
            CalibrationData object

        Raises:
            RuntimeError: If not calibrated
        """
        if not self.is_calibrated():
            raise RuntimeError("No calibration loaded.")
        return self._calibration

    def calibrate_from_detections(
        self,
        camera_frame: np.ndarray,
        projector_resolution: Resolution,
        camera_resolution: Resolution,
        known_marker_positions: dict
    ) -> CalibrationData:
        """
        Run calibration from a single camera frame with visible markers.

        Args:
            camera_frame: Camera image with visible calibration pattern
            projector_resolution: Projector resolution
            camera_resolution: Camera resolution
            known_marker_positions: Dict mapping marker_id -> Point2D in projector coords

        Returns:
            CalibrationData with transformation and quality metrics

        Raises:
            RuntimeError: If calibration fails
        """
        # Detect markers in camera frame
        detector = ArucoPatternDetector(self.config.aruco_dict)
        detections, success = detector.detect_markers(
            camera_frame,
            expected_ids=list(known_marker_positions.keys())
        )

        if not success or len(detections) < self.config.min_markers_required:
            raise RuntimeError(
                f"Insufficient markers detected: {len(detections)} "
                f"(minimum required: {self.config.min_markers_required})"
            )

        print(f"Detected {len(detections)} markers in camera view")

        # Create point correspondences
        camera_points, projector_points = detector.create_point_correspondences(
            detections,
            known_marker_positions
        )

        if len(camera_points) < self.config.min_markers_required:
            raise RuntimeError(
                f"Insufficient matching markers: {len(camera_points)} "
                f"(minimum required: {self.config.min_markers_required})"
            )

        print(f"Matched {len(camera_points)} marker pairs")

        # Compute homography
        H, inlier_mask, quality = compute_homography(
            camera_points,
            projector_points,
            ransac_threshold=self.config.ransac_threshold
        )

        print(f"Homography computed:")
        print(f"  RMS error: {quality.reprojection_error_rms:.2f}px")
        print(f"  Max error: {quality.reprojection_error_max:.2f}px")
        print(f"  Inliers: {quality.num_inliers}/{quality.num_total_points}")

        # Check quality
        if quality.reprojection_error_rms > self.config.max_reprojection_error:
            print(f"WARNING: Calibration quality below threshold!")
            print(f"  RMS error {quality.reprojection_error_rms:.2f}px > "
                  f"{self.config.max_reprojection_error:.2f}px")

        # Store homography matrices first (needed for screen bounds computation)
        self._H_cam_to_proj = H.to_numpy()
        self._H_proj_to_cam = np.linalg.inv(self._H_cam_to_proj)

        # Compute screen bounds in camera space
        # This defines the area of the camera frame that maps to the projected screen
        screen_bounds = self._compute_screen_bounds(projector_resolution)
        print(f"Screen bounds computed (camera pixel coords):")
        print(f"  Top-left: ({screen_bounds.top_left.x:.1f}, {screen_bounds.top_left.y:.1f})")
        print(f"  Top-right: ({screen_bounds.top_right.x:.1f}, {screen_bounds.top_right.y:.1f})")
        print(f"  Bottom-right: ({screen_bounds.bottom_right.x:.1f}, {screen_bounds.bottom_right.y:.1f})")
        print(f"  Bottom-left: ({screen_bounds.bottom_left.x:.1f}, {screen_bounds.bottom_left.y:.1f})")

        # Create calibration data
        calibration_data = CalibrationData(
            timestamp=datetime.now(),
            projector_resolution=projector_resolution,
            camera_resolution=camera_resolution,
            homography_camera_to_projector=H,
            quality=quality,
            detection_method=f"aruco_{self.config.grid_size[0]}x{self.config.grid_size[1]}",
            num_calibration_points=len(camera_points),
            screen_bounds=screen_bounds
        )

        # Store calibration
        self._calibration = calibration_data

        # Auto-save if configured
        if self.config.auto_save:
            self._auto_save_calibration(calibration_data)

        return calibration_data

    def _auto_save_calibration(self, calibration: CalibrationData):
        """Save calibration with automatic filename."""
        calib_dir = Path(self.config.calibration_dir)
        calib_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = calibration.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"calibration_{timestamp_str}.json"
        filepath = calib_dir / filename

        calibration.save(str(filepath))
        print(f"Saved calibration to {filepath}")

        # Cleanup old calibrations
        self._cleanup_old_calibrations(calib_dir)

    def _cleanup_old_calibrations(self, calib_dir: Path):
        """Keep only N most recent calibration files."""
        calibration_files = sorted(
            calib_dir.glob("calibration_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        # Keep only the most recent N files
        for old_file in calibration_files[self.config.keep_history:]:
            old_file.unlink()
            print(f"Removed old calibration: {old_file.name}")


if __name__ == "__main__":
    # Example usage
    config = CalibrationConfig(
        aruco_dict="DICT_4X4_50",
        grid_size=(4, 4),
        min_markers_required=12,
        calibration_dir="./calibration_data"
    )

    manager = CalibrationManager(config)

    print(f"Calibration manager initialized")
    print(f"  Is calibrated: {manager.is_calibrated()}")
    print(f"  Config: {config.grid_size[0]}x{config.grid_size[1]} grid")
    print(f"\nTo run calibration:")
    print(f"  1. Project calibration pattern onto target surface")
    print(f"  2. Capture camera frame")
    print(f"  3. Call manager.calibrate_from_detections()")
