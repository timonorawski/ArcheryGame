"""
Object Detection Backend for AMS.

Detects physical objects (nerf darts, arrows, balls) and registers impacts.
Uses pluggable object detectors and ArUco calibration.
"""

import cv2
from ams.logging import get_logger
import math
import numpy as np
import time
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

from ams.detection_backend import DetectionBackend
from ams.camera import CameraInterface
from ams.events import PlaneHitEvent, CalibrationResult
from calibration.calibration_manager import CalibrationManager
from models import Point2D

log = get_logger('object_detection_backend')
from .object_detection import (
    ObjectDetector,
    DetectedObject,
    ImpactEvent,
    ColorBlobDetector,
    ColorBlobConfig,
    ImpactMode,
)


@dataclass
class TrackedObject:
    """Tracked object with history for impact detection."""
    object_id: int
    last_detection: DetectedObject
    stationary_since: Optional[float] = None  # When it became stationary (STATIONARY mode)
    stationary_frames: int = 0                 # Consecutive stationary frames (STUCK mode)
    velocity_history: List[Tuple[float, Point2D]] = None  # (timestamp, velocity)

    def __post_init__(self):
        if self.velocity_history is None:
            self.velocity_history = []


@dataclass
class HandledObject:
    """A stuck projectile that has been registered (STUCK mode).

    Once a projectile sticks and registers an impact, it's added here
    to prevent duplicate detections. Cleared on round reset.
    """
    position: Point2D           # Impact point in camera coords
    registered_at: float        # Timestamp when registered
    object_id: int              # Tracking ID for reference


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
        impact_mode: ImpactMode = ImpactMode.TRAJECTORY_CHANGE,
        impact_velocity_threshold: float = 10.0,
        impact_duration: float = 0.15,
        velocity_change_threshold: float = 100.0,
        direction_change_threshold: float = 90.0,
        min_impact_velocity: float = 50.0,
    ):
        """Initialize object detection backend.

        Args:
            camera: Camera instance for capturing frames
            detector: Object detector (defaults to ColorBlobDetector)
            calibration_manager: ArUco calibration manager (optional)
            display_width: Display width in pixels
            display_height: Display height in pixels
            impact_mode: Detection mode (TRAJECTORY_CHANGE for bouncing, STATIONARY for sticking)
            impact_velocity_threshold: Speed threshold (px/s) for stationary mode
            impact_duration: Duration (s) object must be stationary for stationary mode
            velocity_change_threshold: Velocity change magnitude (px/s) for trajectory_change mode
            direction_change_threshold: Direction change (degrees) for trajectory_change mode
            min_impact_velocity: Minimum speed before impact (px/s) for trajectory_change mode
        """
        self.camera = camera
        self.detector = detector or ColorBlobDetector()
        self.calibration_manager = calibration_manager
        self.display_width = display_width
        self.display_height = display_height

        # Impact detection mode and parameters
        self.impact_mode = impact_mode

        # Stationary mode parameters
        self.impact_velocity_threshold = impact_velocity_threshold
        self.impact_duration = impact_duration

        # Trajectory change mode parameters
        self.velocity_change_threshold = velocity_change_threshold
        self.direction_change_threshold = direction_change_threshold
        self.min_impact_velocity = min_impact_velocity

        # Tracking state
        self.tracked_objects: Dict[int, TrackedObject] = {}
        self.next_object_id = 0
        self.max_tracking_gap = 0.5  # seconds

        # STUCK mode state
        self._handled_objects: List[HandledObject] = []
        self._stuck_stationary_threshold: float = 5.0  # px/s
        self._stuck_confirm_frames: int = 3
        self._handled_radius: float = 30.0  # px
        self._camera_center_x: Optional[float] = None  # Set after calibration

        # Initialize camera geometry if calibration already loaded
        if self.calibration_manager and self.calibration_manager.is_calibrated():
            geometry = self.calibration_manager.get_camera_geometry()
            if geometry:
                self._camera_center_x = geometry['camera_center_x']

        # Debug visualization
        self.debug_mode = False
        self.debug_frame: Optional[np.ndarray] = None
        self.game_targets: List[Tuple[float, float, float, Tuple[int, int, int]]] = []

    def poll_events(self) -> List[PlaneHitEvent]:
        """Get new detection events since last poll.

        Returns:
            List of hit events from detected impacts
        """
        return self.poll()

    def update(self, dt: float):
        """Update backend state (called each frame).

        For object detection, all processing happens in poll_events(),
        so this is a no-op.

        Args:
            dt: Delta time since last update
        """
        pass

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

        # STUCK mode: check for removed objects (logging only)
        if self.impact_mode == ImpactMode.STUCK and self._handled_objects:
            self._check_removed_objects(detections, timestamp)

        # Convert impacts to hit events
        events = []
        for impact in impacts:
            # Filter out impacts outside the projected screen bounds
            # (camera sees more than just the projection surface)
            if not self._is_within_screen_bounds(impact.position):
                log.debug(
                    f"Filtering out-of-bounds impact at camera ({impact.position.x:.0f}, {impact.position.y:.0f})"
                )
                continue

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

                # Calculate current speed
                speed = math.sqrt(det.velocity.x ** 2 + det.velocity.y ** 2)

                # Get previous velocity for trajectory change detection
                prev_velocity = tracked.last_detection.velocity
                prev_speed = math.sqrt(prev_velocity.x ** 2 + prev_velocity.y ** 2)

                # Impact detection based on mode
                impact_detected = False

                if self.impact_mode == ImpactMode.TRAJECTORY_CHANGE:
                    # Trajectory change mode - detect bounces
                    # Calculate velocity change magnitude
                    velocity_change_mag = math.sqrt(
                        (det.velocity.x - prev_velocity.x) ** 2 +
                        (det.velocity.y - prev_velocity.y) ** 2
                    )

                    # Calculate direction change
                    direction_change = self._calculate_direction_change(prev_velocity, det.velocity)

                    # Check if this looks like an impact (bounce)
                    # Requirements:
                    # 1. Object was moving fast enough before impact
                    # 2. Significant velocity change OR direction change
                    if prev_speed >= self.min_impact_velocity:
                        if (velocity_change_mag >= self.velocity_change_threshold or
                            direction_change >= self.direction_change_threshold):
                            # Detected bounce/impact!
                            impact_detected = True
                            impact = ImpactEvent(
                                position=tracked.last_detection.position,  # Use position before bounce
                                velocity_before=prev_velocity,
                                timestamp=timestamp,
                                stationary_duration=0.0  # N/A for trajectory change mode
                            )
                            impacts.append(impact)

                            # Continue tracking (object bounces off, doesn't stop)

                elif self.impact_mode == ImpactMode.STATIONARY:
                    # Stationary mode - detect when object stops and stays
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
                                impact_detected = True
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

                elif self.impact_mode == ImpactMode.STUCK:
                    # STUCK mode - detect projectiles that embed permanently (arrows, darts)
                    # Register once when stuck, then ignore (added to handled list)
                    is_stationary = speed < self._stuck_stationary_threshold

                    if is_stationary:
                        # Increment stationary frame counter
                        tracked.stationary_frames += 1

                        # Check if confirmed stuck (enough consecutive stationary frames)
                        if tracked.stationary_frames >= self._stuck_confirm_frames:
                            # Get impact point from contour (tip, not tail)
                            impact_pos = self._get_impact_point(det.contour, det.position)

                            # Check if this location already has a handled object
                            if not self._is_handled(impact_pos):
                                # NEW IMPACT - projectile just stuck!
                                impact_detected = True
                                impact = ImpactEvent(
                                    position=impact_pos,
                                    velocity_before=tracked.last_detection.velocity,
                                    timestamp=timestamp,
                                    stationary_duration=tracked.stationary_frames / 30.0  # Approx seconds
                                )
                                impacts.append(impact)

                                # Add to handled list to prevent duplicate detection
                                self._add_handled(impact_pos, tracked.object_id, timestamp)

                            # Keep tracking (object stays visible but won't trigger again)
                    else:
                        # Object is moving, reset stationary counter
                        tracked.stationary_frames = 0

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

    def _calculate_direction_change(self, v1: Point2D, v2: Point2D) -> float:
        """Calculate angle change between two velocity vectors.

        Args:
            v1: Previous velocity vector
            v2: Current velocity vector

        Returns:
            Angle change in degrees (0-180)
        """
        # Calculate magnitudes
        mag1 = math.sqrt(v1.x ** 2 + v1.y ** 2)
        mag2 = math.sqrt(v2.x ** 2 + v2.y ** 2)

        # Avoid division by zero
        if mag1 < 1.0 or mag2 < 1.0:
            return 0.0

        # Calculate dot product
        dot = v1.x * v2.x + v1.y * v2.y

        # Calculate cosine of angle
        cos_angle = dot / (mag1 * mag2)

        # Clamp to valid range for acos
        cos_angle = max(-1.0, min(1.0, cos_angle))

        # Calculate angle in radians, then convert to degrees
        angle_rad = math.acos(cos_angle)
        angle_deg = math.degrees(angle_rad)

        return angle_deg

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

    def _is_within_screen_bounds(self, camera_pos: Point2D) -> bool:
        """Check if a camera-space point is within the projected screen area.

        The camera typically sees more than just the projection surface.
        This method filters out detections that fall outside the active
        game area (outside the projected screen).

        Args:
            camera_pos: Position in camera pixel coordinates

        Returns:
            True if within bounds, False otherwise
        """
        if self.calibration_manager is None:
            return True  # No calibration = no filtering

        return self.calibration_manager.is_within_screen_bounds(camera_pos)

    # =========================================================================
    # STUCK Mode Methods
    # =========================================================================

    def _is_handled(self, position: Point2D) -> bool:
        """Check if position matches any handled (already registered) stuck object.

        Args:
            position: Position to check in camera coordinates

        Returns:
            True if this position already has a registered stuck object
        """
        for handled in self._handled_objects:
            dx = position.x - handled.position.x
            dy = position.y - handled.position.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < self._handled_radius:
                return True
        return False

    def _add_handled(self, position: Point2D, object_id: int, timestamp: float) -> None:
        """Add a new handled stuck object.

        Args:
            position: Impact position in camera coordinates
            object_id: Tracking ID of the object
            timestamp: Time of registration
        """
        self._handled_objects.append(HandledObject(
            position=position,
            registered_at=timestamp,
            object_id=object_id
        ))
        log.debug(f"Added handled stuck object at ({position.x:.0f}, {position.y:.0f})")

    def reset_handled_objects(self) -> None:
        """Clear all handled stuck objects.

        Call this on round reset when user clears the target.
        """
        count = len(self._handled_objects)
        self._handled_objects.clear()
        if count > 0:
            log.info(f"Cleared {count} handled stuck objects")

    def _get_impact_point(self, contour: Optional[np.ndarray], detection_pos: Point2D) -> Point2D:
        """Estimate true impact point from contour based on camera viewing angle.

        For stuck projectiles (arrows, darts), the detected blob is the tail/fletching,
        but the actual impact point is the tip. Based on camera position:
        - If detection is LEFT of camera center → tip is RIGHTMOST point
        - If detection is RIGHT of camera center → tip is LEFTMOST point

        Args:
            contour: Contour points from blob detection
            detection_pos: Center position of detected blob

        Returns:
            Estimated impact point (tip position)
        """
        # Fallback to center if no contour or camera geometry
        if contour is None or self._camera_center_x is None:
            return detection_pos

        try:
            points = contour.reshape(-1, 2)

            if len(points) < 3:
                return detection_pos

            if detection_pos.x < self._camera_center_x:
                # Detection left of camera → arrow points right → rightmost is tip
                idx = np.argmax(points[:, 0])
            else:
                # Detection right of camera → arrow points left → leftmost is tip
                idx = np.argmin(points[:, 0])

            return Point2D(x=float(points[idx, 0]), y=float(points[idx, 1]))
        except Exception as e:
            log.warning(f"Impact point estimation failed: {e}")
            return detection_pos

    def _check_removed_objects(self, current_detections: List[DetectedObject], timestamp: float) -> None:
        """Check if any handled stuck objects have been removed (arrow pulled out).

        Logs removal for debugging/future use but does not generate game events.

        Args:
            current_detections: Current frame's detected objects
            timestamp: Current timestamp
        """
        min_age = 1.0  # Object must be at least 1s old to count as "removed"

        for handled in self._handled_objects:
            # Check if object has been there long enough to consider removal
            if (timestamp - handled.registered_at) < min_age:
                continue

            # Check if still visible (any detection near handled position)
            still_visible = any(
                math.sqrt((handled.position.x - det.position.x) ** 2 +
                         (handled.position.y - det.position.y) ** 2) < self._handled_radius
                for det in current_detections
            )

            if not still_visible:
                log.info(
                    f"Stuck object may have been removed at "
                    f"({handled.position.x:.0f}, {handled.position.y:.0f})"
                )

    def _is_valid_coordinate(self, pos: Point2D) -> bool:
        """Check if coordinate is valid (no NaN, infinity, within game bounds).

        Args:
            pos: Position to validate

        Returns:
            True if valid (within [0, 1] range), False otherwise
        """
        if not (math.isfinite(pos.x) and math.isfinite(pos.y)):
            return False

        # Strictly enforce [0, 1] bounds for game coordinates
        if not (0.0 <= pos.x <= 1.0 and 0.0 <= pos.y <= 1.0):
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

    def calibrate(self, display_surface=None, display_resolution=None, **kwargs) -> CalibrationResult:
        """Run ArUco calibration for geometric mapping.

        Args:
            display_surface: Pygame surface to display calibration pattern
            display_resolution: (width, height) of display
            **kwargs: Additional calibration parameters

        Returns:
            Calibration result
        """
        # Import calibration dependencies
        try:
            import pygame
            from datetime import datetime
            from models import (
                CalibrationConfig,
                Resolution,
                CalibrationData,
                HomographyMatrix,
            )
            from calibration.pattern_generator import ArucoPatternGenerator
            from calibration.pattern_detector import ArucoPatternDetector
            from calibration.homography import compute_homography
        except ImportError as e:
            log.warning(f"Calibration dependencies not available: {e}")
            import traceback
            traceback.print_exc()
            return self._return_no_calibration()

        if display_surface is None or display_resolution is None:
            log.warning("No display surface provided, skipping geometric calibration")
            return self._return_no_calibration()

        print("\n" + "="*60)
        print("ArUco Geometric Calibration")
        print("="*60)
        print("\nInstructions:")
        print("1. ArUco marker pattern will be displayed")
        print("2. Position camera to see entire pattern")
        print("3. Press SPACE to capture and calibrate")
        print("4. Press ESC to skip calibration")
        print("\nStarting in 3 seconds...")

        import time
        time.sleep(3)

        # Initialize
        config = CalibrationConfig()
        pattern_generator = ArucoPatternGenerator(config.aruco_dict)

        # Generate pattern
        proj_resolution = Resolution(width=display_resolution[0], height=display_resolution[1])
        calibration_pattern, marker_positions = pattern_generator.generate_grid(
            proj_resolution,
            grid_size=config.grid_size,
            margin_percent=config.margin_percent
        )

        # Convert to pygame surface
        pattern_rgb = cv2.cvtColor(calibration_pattern, cv2.COLOR_BGR2RGB)
        pattern_surface = pygame.surfarray.make_surface(pattern_rgb.swapaxes(0, 1))

        # Display pattern and wait for capture
        captured = False
        camera_frame = None

        print("\nLIVE CAMERA PREVIEW:")
        print("  - Position camera to see entire pattern")
        print("  - Wait for marker count to reach 12+ (shown in preview window)")
        print("  - Press SPACE when markers are detected")
        print("  - Press ESC to skip calibration")

        # Import detector for live preview
        detector = ArucoPatternDetector(config.aruco_dict)

        clock = pygame.time.Clock()
        while not captured:
            # Display pattern on projector/display
            display_surface.blit(pattern_surface, (0, 0))

            # Add instruction text on projector
            font = pygame.font.Font(None, 36)
            text = font.render("SPACE=Capture  ESC=Skip", True, (0, 255, 0))
            display_surface.blit(text, (20, 20))

            pygame.display.flip()

            # Show live camera preview with marker detection
            frame = self.camera.capture_frame()
            detected_markers, _ = detector.detect_markers(frame)

            # Draw detected markers on preview
            preview = frame.copy()
            for marker in detected_markers:
                # Draw marker corners
                corners = [(int(c.x), int(c.y)) for c in marker.corners]
                cv2.polylines(preview, [np.array(corners)], True, (0, 255, 0), 2)
                # Draw marker ID
                center = (int(marker.center.x), int(marker.center.y))
                cv2.putText(preview, str(marker.marker_id), center,
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # Add marker count with color coding
            count = len(detected_markers)
            total = len(marker_positions)
            color = (0, 255, 0) if count >= config.min_markers_required else (0, 0, 255)
            cv2.putText(preview, f"Detected: {count}/{total} markers", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            # Add instructions
            status = "READY" if count >= config.min_markers_required else "ADJUST CAMERA"
            cv2.putText(preview, f"Status: {status}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.putText(preview, "SPACE=Capture  ESC=Skip", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            cv2.imshow("ArUco Calibration - Camera Preview", preview)

            # Handle pygame events
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        # Capture current frame (already in 'frame' variable)
                        camera_frame = frame
                        captured = True
                        print(f"Frame captured! Detected {count} markers")
                    elif event.key == pygame.K_ESCAPE:
                        print("Calibration skipped")
                        cv2.destroyAllWindows()
                        return self._return_no_calibration()

            # Also handle CV window events
            key = cv2.waitKey(1) & 0xFF
            if key == 32:  # SPACE
                camera_frame = frame
                captured = True
                print(f"Frame captured! Detected {count} markers")
            elif key == 27:  # ESC
                print("Calibration skipped")
                cv2.destroyAllWindows()
                return self._return_no_calibration()

            clock.tick(30)

        cv2.destroyAllWindows()

        # Safety check
        if camera_frame is None:
            print("ERROR: No frame captured")
            return self._return_no_calibration()

        # Detect markers in captured frame (detector already created above)
        detected_markers, _ = detector.detect_markers(camera_frame)

        if len(detected_markers) < 4:
            print(f"ERROR: Only {len(detected_markers)} markers detected, need at least 4")
            return self._return_no_calibration()

        print(f"Detected {len(detected_markers)} markers")

        # Create point correspondences (match detected markers with known positions)
        camera_points, projector_points = detector.create_point_correspondences(
            detected_markers,
            marker_positions
        )

        print(f"Matched {len(camera_points)} point pairs for homography computation")

        if len(camera_points) < 4:
            print(f"ERROR: Need at least 4 matched pairs, got {len(camera_points)}")
            return self._return_no_calibration()

        # Compute homography
        try:
            homography, inlier_mask, quality = compute_homography(camera_points, projector_points)

            print(f"Homography computed successfully!")
            print(f"  RMS error: {quality.reprojection_error_rms:.2f}px")
            print(f"  Max error: {quality.reprojection_error_max:.2f}px")
            print(f"  Inliers: {quality.num_inliers}/{quality.num_total_points}")
            print(f"  Quality: {'GOOD' if quality.is_acceptable else 'POOR'}")

            # Step 2: Run projectile color detection
            print("\n" + "-" * 60)
            print("Press SPACE to continue to projectile color detection...")
            print("Press ESC to skip color detection and use defaults")
            print("-" * 60)

            # Wait for user to press SPACE or ESC
            waiting = True
            skip_color_detection = False
            while waiting:
                display_surface.fill((0, 0, 0))
                font = pygame.font.Font(None, 48)

                # Show calibration success message
                text1 = font.render("Geometric Calibration Complete!", True, (0, 255, 0))
                text2 = font.render(f"RMS Error: {quality.reprojection_error_rms:.2f}px", True, (255, 255, 255))
                text3 = font.render("SPACE = Detect Projectile Color", True, (255, 255, 0))
                text4 = font.render("ESC = Skip (use defaults)", True, (128, 128, 128))

                y_offset = display_resolution[1] // 2 - 100
                for i, text in enumerate([text1, text2, text3, text4]):
                    rect = text.get_rect(center=(display_resolution[0] // 2, y_offset + i * 60))
                    display_surface.blit(text, rect)

                pygame.display.flip()

                for event in pygame.event.get():
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_SPACE:
                            waiting = False
                        elif event.key == pygame.K_ESCAPE:
                            waiting = False
                            skip_color_detection = True

                key = cv2.waitKey(1) & 0xFF
                if key == 32:  # SPACE
                    waiting = False
                elif key == 27:  # ESC
                    waiting = False
                    skip_color_detection = True

                clock.tick(30)

            # Run color detection if not skipped
            detected_color_config = None
            color_detection_notes = ""
            if not skip_color_detection:
                detected_color_config = self._run_projectile_color_detection(
                    display_surface,
                    display_resolution,
                    pygame
                )

                if detected_color_config:
                    # Update the detector with new color config
                    self.detector.configure(
                        hue_min=detected_color_config.hue_min,
                        hue_max=detected_color_config.hue_max,
                        saturation_min=detected_color_config.saturation_min,
                        saturation_max=detected_color_config.saturation_max,
                        value_min=detected_color_config.value_min,
                        value_max=detected_color_config.value_max,
                    )
                    color_detection_notes = f" | HSV: H({detected_color_config.hue_min}-{detected_color_config.hue_max})"
                    print("Detector updated with detected color range")

            # Create calibration data
            cam_width, cam_height = self.camera.get_resolution()
            calibration_data = CalibrationData(
                camera_resolution=Resolution(width=cam_width, height=cam_height),
                projector_resolution=proj_resolution,
                homography_camera_to_projector=homography,
                quality=quality,
                calibration_time=datetime.now(),
                marker_count=len(detected_markers)
            )

            # Save calibration (screen_bounds will be computed when loaded)
            calib_path = "calibration.json"
            calibration_data.save(calib_path)
            log.info(f"Calibration saved to {calib_path}")

            # Update calibration manager if available
            if self.calibration_manager:
                self.calibration_manager.load_calibration(calib_path)
                log.debug("Calibration manager updated")

                # Update camera geometry for STUCK mode impact point estimation
                geometry = self.calibration_manager.get_camera_geometry()
                if geometry:
                    self._camera_center_x = geometry['camera_center_x']
                    log.debug(f"Camera center X set to {self._camera_center_x:.1f}")

            return CalibrationResult(
                success=True,
                method="aruco_geometric_calibration",
                available_colors=self._get_default_colors(),
                display_latency_ms=0.0,
                detection_quality=quality.quality_score if quality.quality_score is not None else 1.0,
                notes=f"ArUco calibration: {len(detected_markers)} markers, {quality.reprojection_error_rms:.2f}px RMS error{color_detection_notes}"
            )

        except Exception as e:
            log.error(f"Calibration failed: {e}")
            import traceback
            traceback.print_exc()
            return self._return_no_calibration()

    def _return_no_calibration(self):
        """Return calibration result without geometric calibration."""
        return CalibrationResult(
            success=True,
            method="object_detection_no_geometric_calibration",
            available_colors=self._get_default_colors(),
            display_latency_ms=0.0,
            detection_quality=0.5,  # Reduced quality without calibration
            notes="No geometric calibration performed - using simple coordinate normalization"
        )

    def _run_projectile_color_detection(
        self,
        display_surface,
        display_resolution: tuple,
        pygame_module,
    ) -> Optional[ColorBlobConfig]:
        """Run projectile color detection step.

        Projects white screen and asks user to fire projectiles.
        Detects moving objects and samples their HSV color values.

        Args:
            display_surface: Pygame surface for display
            display_resolution: (width, height) of display
            pygame_module: Reference to pygame module

        Returns:
            ColorBlobConfig with detected HSV range, or None if skipped
        """
        print("\n" + "=" * 60)
        print("Projectile Color Detection")
        print("=" * 60)
        print("\nInstructions:")
        print("1. A white screen will be displayed")
        print("2. Fire 3-5 projectiles across the screen")
        print("3. The system will detect and sample projectile colors")
        print("4. Press SPACE when done, ESC to skip")
        print("\nStarting color detection...")

        # Create white surface
        white_surface = pygame_module.Surface(display_resolution)
        white_surface.fill((255, 255, 255))

        # Tracking state
        hsv_samples = []  # List of (h, s, v) tuples
        motion_threshold = 30  # Minimum pixel movement to detect motion
        prev_frame = None
        prev_gray = None
        sample_cooldown = 0.0  # Prevent sampling same projectile multiple times

        clock = pygame_module.time.Clock()
        running = True

        while running:
            # Display white screen
            display_surface.blit(white_surface, (0, 0))

            # Add instruction text
            font = pygame_module.font.Font(None, 48)
            text = font.render("Fire projectiles! SPACE=Done ESC=Skip", True, (0, 0, 0))
            text_rect = text.get_rect(center=(display_resolution[0] // 2, 50))
            display_surface.blit(text, text_rect)

            # Show sample count
            sample_text = font.render(f"Samples: {len(hsv_samples)}", True, (0, 100, 0))
            display_surface.blit(sample_text, (20, display_resolution[1] - 60))

            pygame_module.display.flip()

            # Capture camera frame
            frame = self.camera.capture_frame()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # Create preview
            preview = frame.copy()
            cam_height, cam_width = frame.shape[:2]

            # Motion detection using frame differencing
            if prev_gray is not None and sample_cooldown <= 0:
                # Calculate absolute difference
                diff = cv2.absdiff(prev_gray, gray)
                _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

                # Find moving regions
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for contour in contours:
                    area = cv2.contourArea(contour)

                    # Filter by size (projectiles are typically 100-5000 pixels)
                    if 100 < area < 5000:
                        # Get bounding box
                        x, y, w, h = cv2.boundingRect(contour)
                        center_x = x + w // 2
                        center_y = y + h // 2

                        # Sample HSV at center of moving object
                        # Take a small region around center for more robust sampling
                        sample_radius = 5
                        y_start = max(0, center_y - sample_radius)
                        y_end = min(cam_height, center_y + sample_radius)
                        x_start = max(0, center_x - sample_radius)
                        x_end = min(cam_width, center_x + sample_radius)

                        if y_end > y_start and x_end > x_start:
                            region = hsv[y_start:y_end, x_start:x_end]
                            mean_hsv = np.mean(region, axis=(0, 1))

                            h_val, s_val, v_val = int(mean_hsv[0]), int(mean_hsv[1]), int(mean_hsv[2])

                            # Filter out white/gray (low saturation) - we want colored projectiles
                            if s_val > 50:  # Require some saturation
                                hsv_samples.append((h_val, s_val, v_val))
                                sample_cooldown = 0.3  # 300ms cooldown

                                print(f"  Sample {len(hsv_samples)}: H={h_val} S={s_val} V={v_val}")

                                # Draw detection on preview
                                cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 0), 3)
                                cv2.circle(preview, (center_x, center_y), 10, (0, 0, 255), -1)
                                cv2.putText(preview, f"H:{h_val} S:{s_val} V:{v_val}",
                                           (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # Update cooldown
            sample_cooldown = max(0, sample_cooldown - 1/30)

            # Draw motion detection areas
            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(preview, contours, -1, (255, 255, 0), 1)

            # Show info on preview
            cv2.putText(preview, f"Samples: {len(hsv_samples)} | SPACE=Done ESC=Skip",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Show current HSV range if we have samples
            if hsv_samples:
                h_vals = [s[0] for s in hsv_samples]
                s_vals = [s[1] for s in hsv_samples]
                v_vals = [s[2] for s in hsv_samples]

                h_min, h_max = min(h_vals), max(h_vals)
                s_min, s_max = min(s_vals), max(s_vals)
                v_min, v_max = min(v_vals), max(v_vals)

                cv2.putText(preview, f"H: {h_min}-{h_max} | S: {s_min}-{s_max} | V: {v_min}-{v_max}",
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            cv2.imshow("Projectile Color Detection", preview)

            # Store current frame for next iteration
            prev_gray = gray.copy()
            prev_frame = frame.copy()

            # Handle pygame events
            for event in pygame_module.event.get():
                if event.type == pygame_module.KEYDOWN:
                    if event.key == pygame_module.K_SPACE:
                        running = False
                    elif event.key == pygame_module.K_ESCAPE:
                        print("Color detection skipped")
                        cv2.destroyAllWindows()
                        return None

            # Handle CV window events
            key = cv2.waitKey(1) & 0xFF
            if key == 32:  # SPACE
                running = False
            elif key == 27:  # ESC
                print("Color detection skipped")
                cv2.destroyAllWindows()
                return None

            clock.tick(30)

        cv2.destroyAllWindows()

        # Process samples and create config
        if len(hsv_samples) < 2:
            print("Not enough samples collected, using defaults")
            return None

        # Calculate HSV range from samples with some padding
        h_vals = [s[0] for s in hsv_samples]
        s_vals = [s[1] for s in hsv_samples]
        v_vals = [s[2] for s in hsv_samples]

        # Add padding to range (HSV detection works better with some tolerance)
        h_padding = 10
        s_padding = 30
        v_padding = 30

        h_min = max(0, min(h_vals) - h_padding)
        h_max = min(179, max(h_vals) + h_padding)
        s_min = max(0, min(s_vals) - s_padding)
        s_max = min(255, max(s_vals) + s_padding)
        v_min = max(0, min(v_vals) - v_padding)
        v_max = 255  # Always allow bright objects

        print(f"\nDetected HSV range:")
        print(f"  Hue: {h_min} - {h_max}")
        print(f"  Saturation: {s_min} - {s_max}")
        print(f"  Value: {v_min} - {v_max}")

        config = ColorBlobConfig(
            hue_min=h_min,
            hue_max=h_max,
            saturation_min=s_min,
            saturation_max=s_max,
            value_min=v_min,
            value_max=v_max,
        )

        return config

    def _get_default_colors(self):
        """Get default color palette."""
        return [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (255, 128, 0),  # Orange
            (128, 0, 255),  # Purple
            (0, 255, 128),  # Spring Green
            (255, 255, 255) # White
        ]

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
