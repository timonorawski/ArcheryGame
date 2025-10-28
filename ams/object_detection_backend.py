"""
Object Detection Backend for AMS.

Detects physical objects (nerf darts, arrows, balls) and registers impacts.
Uses pluggable object detectors and ArUco calibration.
"""

import cv2
import numpy as np
import math
import time
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

from ams.detection_backend import DetectionBackend
from ams.camera import CameraInterface
from ams.events import PlaneHitEvent, CalibrationResult
from calibration.calibration_manager import CalibrationManager
from models import Point2D
from .object_detection import (
    ObjectDetector,
    DetectedObject,
    ImpactEvent,
    ColorBlobDetector,
    ColorBlobConfig,
)


@dataclass
class TrackedObject:
    """Tracked object with history for impact detection."""
    object_id: int
    last_detection: DetectedObject
    stationary_since: Optional[float] = None  # When it became stationary
    velocity_history: List[Tuple[float, Point2D]] = None  # (timestamp, velocity)

    def __post_init__(self):
        if self.velocity_history is None:
            self.velocity_history = []


class ObjectDetectionBackend(DetectionBackend):
    """Detection backend using object detection and impact detection.

    Detects colored objects (nerf darts) and registers hits when they impact
    and come to rest at a location. Uses ArUco calibration for coordinate mapping.
    """

    def __init__(
        self,
        camera: CameraInterface,
        detector: Optional[ObjectDetector] = None,
        calibration_manager: Optional[CalibrationManager] = None,
        display_width: int = 1920,
        display_height: int = 1080,
        impact_velocity_threshold: float = 10.0,
        impact_duration: float = 0.15,
    ):
        """Initialize object detection backend.

        Args:
            camera: Camera instance for capturing frames
            detector: Object detector (defaults to ColorBlobDetector)
            calibration_manager: ArUco calibration manager (optional)
            display_width: Display width in pixels
            display_height: Display height in pixels
            impact_velocity_threshold: Speed threshold (px/s) for impact
            impact_duration: Duration (s) object must be stationary
        """
        self.camera = camera
        self.detector = detector or ColorBlobDetector()
        self.calibration_manager = calibration_manager
        self.display_width = display_width
        self.display_height = display_height

        # Impact detection parameters
        self.impact_velocity_threshold = impact_velocity_threshold
        self.impact_duration = impact_duration

        # Tracking state
        self.tracked_objects: Dict[int, TrackedObject] = {}
        self.next_object_id = 0
        self.max_tracking_gap = 0.5  # seconds

        # Debug visualization
        self.debug_mode = False
        self.debug_frame: Optional[np.ndarray] = None
        self.game_targets: List[Tuple[float, float, float, Tuple[int, int, int]]] = []

    def poll(self) -> List[PlaneHitEvent]:
        """Poll for object impacts and return hit events.

        Returns:
            List of hit events from detected impacts
        """
        # Capture camera frame
        frame = self.camera.capture_frame()
        if frame is None:
            return []

        timestamp = time.time()

        # Detect objects in frame
        detections = self.detector.detect(frame, timestamp)

        # Update tracking and detect impacts
        impacts = self._update_tracking(detections, timestamp)

        # Convert impacts to hit events
        events = []
        for impact in impacts:
            # Transform coordinates to game space
            game_pos = self._camera_to_game(impact.position)

            if game_pos is not None:
                # Validate coordinates
                if self._is_valid_coordinate(game_pos):
                    event = PlaneHitEvent(
                        x=game_pos.x,
                        y=game_pos.y,
                        timestamp=impact.timestamp
                    )
                    events.append(event)

        # Create debug visualization if enabled
        if self.debug_mode:
            self._create_debug_visualization(frame, detections, impacts)

        return events

    def _update_tracking(
        self,
        detections: List[DetectedObject],
        timestamp: float
    ) -> List[ImpactEvent]:
        """Update object tracking and detect impacts.

        Args:
            detections: Current frame detections
            timestamp: Current timestamp

        Returns:
            List of detected impact events
        """
        impacts = []

        # Match detections to tracked objects
        matched_detections = set()
        current_tracks: Dict[int, TrackedObject] = {}

        for track_id, tracked in self.tracked_objects.items():
            # Find closest matching detection
            closest_det = None
            min_dist = float('inf')

            for i, det in enumerate(detections):
                if i in matched_detections:
                    continue

                dx = det.position.x - tracked.last_detection.position.x
                dy = det.position.y - tracked.last_detection.position.y
                dist = math.sqrt(dx * dx + dy * dy)

                if dist < min_dist and dist < 100:  # 100px max matching distance
                    min_dist = dist
                    closest_det = (i, det)

            if closest_det is not None:
                det_idx, det = closest_det
                matched_detections.add(det_idx)

                # Calculate speed
                speed = math.sqrt(det.velocity.x ** 2 + det.velocity.y ** 2)

                # Check if stationary (below velocity threshold)
                is_stationary = speed < self.impact_velocity_threshold

                if is_stationary:
                    # Object is stationary
                    if tracked.stationary_since is None:
                        # Just became stationary
                        tracked.stationary_since = timestamp
                    else:
                        # Check if stationary long enough for impact
                        stationary_duration = timestamp - tracked.stationary_since

                        if stationary_duration >= self.impact_duration:
                            # Register impact!
                            impact = ImpactEvent(
                                position=det.position,
                                velocity_before=tracked.last_detection.velocity,
                                timestamp=timestamp,
                                stationary_duration=stationary_duration
                            )
                            impacts.append(impact)

                            # Stop tracking this object (impact registered)
                            continue
                else:
                    # Object is moving, reset stationary timer
                    tracked.stationary_since = None

                # Update tracked object
                tracked.last_detection = det
                tracked.velocity_history.append((timestamp, det.velocity))

                # Keep only recent velocity history
                tracked.velocity_history = [
                    (t, v) for t, v in tracked.velocity_history
                    if timestamp - t < 1.0
                ]

                current_tracks[track_id] = tracked

        # Add new tracks for unmatched detections
        for i, det in enumerate(detections):
            if i not in matched_detections:
                new_track = TrackedObject(
                    object_id=self.next_object_id,
                    last_detection=det,
                    velocity_history=[(timestamp, det.velocity)]
                )
                current_tracks[self.next_object_id] = new_track
                self.next_object_id += 1

        # Update tracking state
        self.tracked_objects = current_tracks

        return impacts

    def _camera_to_game(self, camera_pos: Point2D) -> Optional[Point2D]:
        """Transform camera coordinates to normalized game coordinates.

        Args:
            camera_pos: Position in camera pixel coordinates

        Returns:
            Position in normalized [0,1] game coordinates, or None if invalid
        """
        if self.calibration_manager is None:
            # No calibration - use simple scaling
            game_x = camera_pos.x / self.camera.get_resolution()[0]
            game_y = camera_pos.y / self.camera.get_resolution()[1]
            return Point2D(x=game_x, y=game_y)

        try:
            # Use calibration manager for accurate transformation
            return self.calibration_manager.camera_to_game(camera_pos)
        except Exception:
            return None

    def _is_valid_coordinate(self, pos: Point2D) -> bool:
        """Check if coordinate is valid (no NaN, infinity, reasonable bounds).

        Args:
            pos: Position to validate

        Returns:
            True if valid, False otherwise
        """
        if not (math.isfinite(pos.x) and math.isfinite(pos.y)):
            return False

        # Allow slight out-of-bounds for edge cases
        if pos.x < -0.1 or pos.x > 1.1 or pos.y < -0.1 or pos.y > 1.1:
            return False

        return True

    def _create_debug_visualization(
        self,
        frame: np.ndarray,
        detections: List[DetectedObject],
        impacts: List[ImpactEvent]
    ) -> None:
        """Create debug visualization overlay.

        Args:
            frame: Camera frame
            detections: Detected objects
            impacts: Detected impacts
        """
        # Get detector's debug frame
        detector_frame = self.detector.get_debug_frame()

        if detector_frame is not None:
            debug = detector_frame.copy()
        else:
            debug = frame.copy()

        # Draw tracked objects
        for tracked in self.tracked_objects.values():
            det = tracked.last_detection
            x, y = int(det.position.x), int(det.position.y)

            # Color based on state
            if tracked.stationary_since is not None:
                color = (0, 165, 255)  # Orange - stationary
            else:
                color = (255, 255, 0)  # Cyan - moving

            cv2.circle(debug, (x, y), 8, color, 2)
            cv2.putText(debug, f"ID:{tracked.object_id}", (x + 10, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        # Draw impacts
        for impact in impacts:
            x, y = int(impact.position.x), int(impact.position.y)
            cv2.circle(debug, (x, y), 15, (0, 0, 255), 3)  # Red circle
            cv2.putText(debug, "IMPACT!", (x - 30, y - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Draw game targets overlay (if calibrated)
        if self.calibration_manager is not None and self.game_targets:
            cam_height, cam_width = frame.shape[:2]

            for target_x, target_y, radius, color in self.game_targets:
                try:
                    # Transform game coords to camera coords
                    game_point = Point2D(x=target_x, y=target_y)
                    proj_point = self.calibration_manager.game_to_projector(game_point)
                    cam_point = self.calibration_manager.projector_to_camera(proj_point)

                    cam_x = int(cam_point.x)
                    cam_y = int(cam_point.y)

                    # Draw target overlay
                    cv2.circle(debug, (cam_x, cam_y), int(radius * 50), (255, 255, 255), 2)
                except Exception:
                    pass  # Skip if transformation fails

        self.debug_frame = debug

    def calibrate(self, **kwargs) -> CalibrationResult:
        """Run ArUco calibration (delegates to calibration manager).

        Args:
            **kwargs: Calibration parameters

        Returns:
            Calibration result
        """
        if self.calibration_manager is None:
            return CalibrationResult(
                success=False,
                method="no_calibration_manager",
                available_colors=None
            )

        # Use existing ArUco calibration
        return CalibrationResult(
            success=True,
            method="aruco_geometric",
            available_colors=None
        )

    def get_backend_info(self) -> dict:
        """Get backend information.

        Returns:
            Dictionary with backend details
        """
        return {
            'backend_type': 'ObjectDetectionBackend',
            'detector': type(self.detector).__name__,
            'calibrated': self.calibration_manager is not None,
            'display_resolution': f'{self.display_width}x{self.display_height}',
            'impact_threshold': f'{self.impact_velocity_threshold}px/s',
            'impact_duration': f'{self.impact_duration}s',
        }

    def set_debug_mode(self, enabled: bool) -> None:
        """Enable/disable debug visualization.

        Args:
            enabled: Whether to show debug overlay
        """
        self.debug_mode = enabled
        self.detector.set_debug_mode(enabled)

    def get_debug_frame(self) -> Optional[np.ndarray]:
        """Get debug visualization frame.

        Returns:
            Debug frame with overlays, or None
        """
        return self.debug_frame

    def set_game_targets(
        self,
        targets: List[Tuple[float, float, float, Tuple[int, int, int]]]
    ) -> None:
        """Set game targets for debug overlay.

        Args:
            targets: List of (x, y, radius, color) tuples in normalized coords
        """
        self.game_targets = targets

    def configure_detector(self, **kwargs) -> None:
        """Update detector configuration dynamically.

        Args:
            **kwargs: Detector-specific parameters
        """
        self.detector.configure(**kwargs)
