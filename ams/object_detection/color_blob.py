"""
Color blob detector for nerf darts and other colored objects.
"""

import cv2
import numpy as np
from typing import List, Optional, Dict
import time
import math

from .base import ObjectDetector, DetectedObject
from .config import ColorBlobConfig
from models import Point2D


class ColorBlobDetector(ObjectDetector):
    """Detects colored objects using HSV color filtering.

    Optimized for nerf darts but configurable for any colored object.
    Tracks object velocity for impact detection.
    """

    def __init__(self, config: Optional[ColorBlobConfig] = None):
        """Initialize color blob detector.

        Args:
            config: Configuration for HSV ranges and filtering
        """
        self.config = config or ColorBlobConfig()
        self.debug_mode = False
        self.debug_frame: Optional[np.ndarray] = None

        # Track previous detections for velocity calculation
        self.prev_detections: Dict[int, DetectedObject] = {}
        self.prev_timestamp: Optional[float] = None
        self.next_object_id = 0

    def detect(self, frame: np.ndarray, timestamp: float) -> List[DetectedObject]:
        """Detect colored blobs in frame.

        Args:
            frame: BGR image from camera
            timestamp: Current timestamp

        Returns:
            List of detected objects with positions and velocities
        """
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Create mask for target color
        lower_bound = np.array(self.config.get_hsv_lower())
        upper_bound = np.array(self.config.get_hsv_upper())
        mask = cv2.inRange(hsv, lower_bound, upper_bound)

        # Morphological operations to remove noise
        if self.config.erode_iterations > 0:
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.erode(mask, kernel, iterations=self.config.erode_iterations)

        if self.config.dilate_iterations > 0:
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=self.config.dilate_iterations)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter contours by area and extract objects
        detected_objects = []

        for contour in contours:
            area = cv2.contourArea(contour)

            # Filter by area
            if area < self.config.min_area or area > self.config.max_area:
                continue

            # Get bounding box and center
            x, y, w, h = cv2.boundingRect(contour)
            center_x = x + w / 2
            center_y = y + h / 2

            # Calculate velocity if we have previous detection
            velocity_x = 0.0
            velocity_y = 0.0

            if self.prev_timestamp is not None and timestamp > self.prev_timestamp:
                dt = timestamp - self.prev_timestamp

                # Find closest previous detection (simple nearest neighbor)
                closest_prev = self._find_closest_previous(center_x, center_y)

                if closest_prev is not None:
                    velocity_x = (center_x - closest_prev.position.x) / dt
                    velocity_y = (center_y - closest_prev.position.y) / dt

            # Create detected object
            obj = DetectedObject(
                position=Point2D(x=center_x, y=center_y),
                velocity=Point2D(x=velocity_x, y=velocity_y),
                area=area,
                bounding_box=(x, y, w, h),
                confidence=1.0,  # Simple blob detection has binary confidence
                timestamp=timestamp,
                contour=contour,  # For STUCK mode impact point estimation
            )

            detected_objects.append(obj)

        # Update tracking
        self.prev_detections = {i: obj for i, obj in enumerate(detected_objects)}
        self.prev_timestamp = timestamp

        # Create debug frame if enabled
        if self.debug_mode:
            self._create_debug_frame(frame, mask, detected_objects)

        return detected_objects

    def _find_closest_previous(self, x: float, y: float) -> Optional[DetectedObject]:
        """Find closest previous detection to given position.

        Args:
            x, y: Position to search from

        Returns:
            Closest previous detection or None
        """
        if not self.prev_detections:
            return None

        closest = None
        min_dist = float('inf')

        for obj in self.prev_detections.values():
            dx = x - obj.position.x
            dy = y - obj.position.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < min_dist:
                min_dist = dist
                closest = obj

        # Only return if close enough (within 200 pixels)
        if min_dist < 200:
            return closest

        return None

    def _create_debug_frame(
        self,
        original: np.ndarray,
        mask: np.ndarray,
        detections: List[DetectedObject]
    ) -> None:
        """Create debug visualization frame.

        Args:
            original: Original BGR frame
            mask: Binary mask of detected blobs
            detections: List of detected objects
        """
        # Create 2-panel debug view: original + mask
        debug = original.copy()

        # Draw detected objects
        for obj in detections:
            # Draw bounding box
            x, y, w, h = obj.bounding_box
            cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Draw center point
            cx, cy = int(obj.position.x), int(obj.position.y)
            cv2.circle(debug, (cx, cy), 5, (0, 0, 255), -1)

            # Draw velocity vector
            vx, vy = obj.velocity.x, obj.velocity.y
            speed = math.sqrt(vx * vx + vy * vy)

            if speed > 1.0:  # Only draw if moving
                # Scale velocity for visibility
                scale = 0.1
                end_x = int(cx + vx * scale)
                end_y = int(cy + vy * scale)
                cv2.arrowedLine(debug, (cx, cy), (end_x, end_y), (255, 0, 0), 2)

            # Draw info text
            info_text = f"Area: {int(obj.area)} Speed: {speed:.1f}px/s"
            cv2.putText(debug, info_text, (x, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Convert mask to BGR for side-by-side display
        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

        # Stack horizontally
        self.debug_frame = np.hstack([debug, mask_bgr])

        # Add header labels
        h, w = self.debug_frame.shape[:2]
        cv2.putText(self.debug_frame, "Detection", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(self.debug_frame, "Mask", (w // 2 + 10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    def get_debug_frame(self) -> Optional[np.ndarray]:
        """Get debug visualization frame.

        Returns:
            Debug frame or None if debug mode disabled
        """
        return self.debug_frame

    def set_debug_mode(self, enabled: bool) -> None:
        """Enable/disable debug visualization.

        Args:
            enabled: Whether to generate debug frames
        """
        self.debug_mode = enabled
        if not enabled:
            self.debug_frame = None

    def configure(self, **kwargs) -> None:
        """Update detector configuration dynamically.

        Supported parameters:
            - hue_min, hue_max: HSV hue range (0-179)
            - saturation_min, saturation_max: Saturation range (0-255)
            - value_min, value_max: Value/brightness range (0-255)
            - min_area, max_area: Blob area filtering
            - erode_iterations, dilate_iterations: Morphological ops

        Args:
            **kwargs: Configuration parameters
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
