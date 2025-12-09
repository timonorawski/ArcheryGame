# STUCK Mode Implementation Plan

## Overview

STUCK mode is a new impact detection mode for projectiles that embed permanently in the target (arrows, real darts). Unlike TRAJECTORY_CHANGE (bouncing) or STATIONARY (stops briefly), stuck projectiles:

1. Appear suddenly in frame
2. Stay permanently at impact location
3. Should register ONE hit, then be ignored
4. Are cleared when user resets the round (clears target)

## Key Features

### 1. Handled Object Tracking
- Track stuck projectiles by position
- New stationary object at fresh location = impact
- Same location = already handled, ignore
- Clear on round reset

### 2. Impact Point Estimation
- Camera viewing angle computed at calibration
- For each detection, determine which side of camera centerline
- Use contour extremity (leftmost/rightmost) as true impact point
- More accurate than blob center for angled arrows

### 3. Optional Removal Detection
- Log when stuck object disappears (arrow pulled out)
- Does not generate game event (future use)

---

## Implementation Details

### File: `ams/object_detection/config.py`

Add to ImpactMode enum:
```python
class ImpactMode(str, Enum):
    TRAJECTORY_CHANGE = "trajectory_change"  # Bouncing (nerf darts)
    STATIONARY = "stationary"                # Stops briefly
    STUCK = "stuck"                          # Embeds permanently (arrows, real darts)
```

Add STUCK parameters to ImpactDetectionConfig:
```python
# STUCK mode parameters
stuck_stationary_threshold: float = Field(
    default=5.0,
    ge=0.0,
    description="Velocity threshold (px/s) to consider object stuck"
)
stuck_confirm_frames: int = Field(
    default=3,
    ge=1,
    description="Consecutive frames object must be stationary to confirm stuck"
)
handled_radius: float = Field(
    default=30.0,
    ge=1.0,
    description="Radius (px) to consider same stuck location"
)
```

### File: `calibration/calibration_manager.py`

Add camera geometry computation:
```python
def get_camera_geometry(self) -> Optional[dict]:
    """Get camera viewing geometry for impact point estimation.

    Returns:
        Dictionary with camera_center_x, camera_center_y in camera pixel coords,
        or None if not calibrated.
    """
    if not self.is_calibrated():
        return None

    # Camera optical center (image center)
    cam_center_x = self._calibration.camera_resolution.width / 2
    cam_center_y = self._calibration.camera_resolution.height / 2

    return {
        'camera_center_x': cam_center_x,
        'camera_center_y': cam_center_y,
    }
```

### File: `ams/object_detection_backend.py`

#### New Data Structure
```python
@dataclass
class HandledObject:
    """A stuck projectile that has been registered."""
    position: Point2D           # Impact point in camera coords
    registered_at: float        # Timestamp when registered
    object_id: int              # Tracking ID
```

#### New Instance Variables
```python
# STUCK mode state
self._handled_objects: List[HandledObject] = []
self._handled_radius: float = 30.0  # From config
self._stuck_stationary_threshold: float = 5.0
self._stuck_confirm_frames: int = 3
self._camera_center_x: Optional[float] = None  # Set after calibration
```

#### New Methods

```python
def _is_handled(self, position: Point2D) -> bool:
    """Check if position matches any handled (already registered) object."""
    for handled in self._handled_objects:
        dx = position.x - handled.position.x
        dy = position.y - handled.position.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < self._handled_radius:
            return True
    return False

def _add_handled(self, position: Point2D, object_id: int, timestamp: float):
    """Add a new handled object."""
    self._handled_objects.append(HandledObject(
        position=position,
        registered_at=timestamp,
        object_id=object_id
    ))
    logger.debug(f"Added handled object at ({position.x:.0f}, {position.y:.0f})")

def reset_handled_objects(self):
    """Clear all handled objects. Call on round reset."""
    count = len(self._handled_objects)
    self._handled_objects.clear()
    logger.info(f"Cleared {count} handled stuck objects")

def _get_impact_point(self, contour: np.ndarray, detection_pos: Point2D) -> Point2D:
    """Estimate true impact point from contour based on camera viewing angle.

    If detection is LEFT of camera center → tip is RIGHTMOST point
    If detection is RIGHT of camera center → tip is LEFTMOST point
    """
    if self._camera_center_x is None:
        return detection_pos  # Fallback to center

    points = contour.reshape(-1, 2)

    if detection_pos.x < self._camera_center_x:
        # Detection left of camera → arrow points right → rightmost is tip
        idx = np.argmax(points[:, 0])
    else:
        # Detection right of camera → arrow points left → leftmost is tip
        idx = np.argmin(points[:, 0])

    return Point2D(x=float(points[idx, 0]), y=float(points[idx, 1]))

def _check_removed_objects(self, current_detections: List[DetectedObject], timestamp: float):
    """Check if any handled objects have been removed (arrow pulled out).

    Logs removal but does not generate game event.
    """
    min_age = 1.0  # Object must be at least 1s old to count as "removed"

    for handled in self._handled_objects[:]:  # Copy list for safe iteration
        # Check if still visible
        still_visible = any(
            math.sqrt((handled.position.x - det.position.x)**2 +
                     (handled.position.y - det.position.y)**2) < self._handled_radius
            for det in current_detections
        )

        if not still_visible and (timestamp - handled.registered_at) > min_age:
            logger.info(f"Stuck object removed at ({handled.position.x:.0f}, {handled.position.y:.0f})")
            # Don't remove from list - could reappear briefly
            # Just log for now, could emit event for future use
```

#### STUCK Mode Logic in `_update_tracking()`

Add new branch for STUCK mode:
```python
elif self.impact_mode == ImpactMode.STUCK:
    # STUCK mode: detect new stationary objects, register once, ignore after

    is_stationary = speed < self._stuck_stationary_threshold

    if is_stationary:
        # Increment stationary frame count
        if tracked.stationary_frames is None:
            tracked.stationary_frames = 1
        else:
            tracked.stationary_frames += 1

        # Check if confirmed stuck (enough stationary frames)
        if tracked.stationary_frames >= self._stuck_confirm_frames:
            # Get impact point from contour
            impact_pos = self._get_impact_point(
                det.contour,
                det.position
            ) if det.contour is not None else det.position

            # Check if this location already handled
            if not self._is_handled(impact_pos):
                # NEW IMPACT!
                impact = ImpactEvent(
                    position=impact_pos,
                    velocity_before=tracked.last_detection.velocity,
                    timestamp=timestamp,
                    stationary_duration=tracked.stationary_frames / 30.0  # Approx
                )
                impacts.append(impact)

                # Add to handled list
                self._add_handled(impact_pos, tracked.object_id, timestamp)

            # Keep tracking but don't register again
    else:
        # Object is moving, reset stationary counter
        tracked.stationary_frames = 0
```

#### Update TrackedObject Dataclass
```python
@dataclass
class TrackedObject:
    """Tracked object with history for impact detection."""
    object_id: int
    last_detection: DetectedObject
    stationary_since: Optional[float] = None  # For STATIONARY mode
    stationary_frames: int = 0                 # For STUCK mode
    velocity_history: List[Tuple[float, Point2D]] = None
```

#### Update DetectedObject to Include Contour
In `ams/object_detection/base.py`, ensure contour is available:
```python
@dataclass
class DetectedObject:
    position: Point2D
    velocity: Point2D
    area: float
    bounding_box: Tuple[int, int, int, int]
    confidence: float
    timestamp: float
    contour: Optional[np.ndarray] = None  # Add this field
```

And in `color_blob.py`, pass the contour:
```python
obj = DetectedObject(
    position=Point2D(x=center_x, y=center_y),
    velocity=Point2D(x=velocity_x, y=velocity_y),
    area=area,
    bounding_box=(x, y, w, h),
    confidence=1.0,
    timestamp=timestamp,
    contour=contour  # Add this
)
```

#### Update Calibration to Set Camera Center
After calibration completes:
```python
# After calibration manager is updated
if self.calibration_manager:
    geometry = self.calibration_manager.get_camera_geometry()
    if geometry:
        self._camera_center_x = geometry['camera_center_x']
```

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      STUCK MODE FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Frame N: Detect colored blobs                                  │
│           ↓                                                     │
│  Match to tracked objects (existing logic)                      │
│           ↓                                                     │
│  For each tracked object:                                       │
│           ↓                                                     │
│  ┌─ Is velocity < stuck_threshold? ─┐                          │
│  │                                   │                          │
│  NO                                 YES                         │
│  │                                   │                          │
│  Reset                         Increment                        │
│  stationary_frames             stationary_frames                │
│  │                                   │                          │
│  └──────────────┬────────────────────┘                          │
│                 ↓                                               │
│  ┌─ stationary_frames >= confirm_threshold? ─┐                 │
│  │                                            │                 │
│  NO                                          YES                │
│  │                                            │                 │
│  Continue                              Get impact point         │
│  tracking                              from contour             │
│                                               │                 │
│                                        ┌─ Is handled? ─┐       │
│                                        │               │        │
│                                       YES              NO       │
│                                        │               │        │
│                                     Ignore        REGISTER      │
│                                                   IMPACT!       │
│                                                      │          │
│                                                 Add to          │
│                                                 handled list    │
│                                                                 │
│  ════════════════════════════════════════════════════════════  │
│                                                                 │
│  On Round Reset:                                                │
│      → Call reset_handled_objects()                             │
│      → User clears physical target                              │
│      → Ready for next round                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Testing Plan

1. **Basic stuck detection**: Fire arrow, verify single impact registered
2. **No duplicate detection**: Same arrow doesn't register twice
3. **Multiple arrows**: Fire multiple arrows, each registers once
4. **Impact point accuracy**: Verify tip detection vs blob center
5. **Round reset**: Clear handled objects, verify new arrows detected
6. **Removal logging**: Pull arrow out, verify log message

---

## Future Enhancements

1. **Impact point for other modes**: Extend `_get_impact_point()` to TRAJECTORY_CHANGE
2. **Removal events**: Emit `ProjectileRemovedEvent` for game logic
3. **Per-arrow tracking**: Track individual arrows through entire lifecycle
4. **Vertical viewing angle**: Handle cameras above/below (top/bottom extremity)
