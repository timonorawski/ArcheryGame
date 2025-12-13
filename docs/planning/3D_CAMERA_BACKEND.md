# 3D Camera Detection Backend Implementation Plan

## Overview

Add depth-aware detection backends to YAMS supporting multiple Kinect generations and three detection modes: depth-filtered impacts, body occlusion, and skeleton tracking.

### Use Cases

**Depth-Filtered Impacts**
- Filter projectile detection to only register hits on the target surface plane
- Eliminates false positives from objects at wrong depth (floor, background, etc.)
- More precise hit registration for archery and throwing games

**Body Occlusion Detection**
- Detect when player's body blocks projected patterns
- Enables laser maze games (jump over/duck under projected "beams")
- Physically interactive sidescrollers where body controls character
- Dance/movement games with projected visual feedback

**Skeleton Tracking**
- Track body joint positions for gesture-based games
- Full-body interactive experiences
- Pose detection for training feedback

---

## Class Hierarchy

```
CameraInterface (existing)              DetectionBackend (existing)
    |                                       |
    +-- OpenCVCamera (existing)             +-- LaserDetectionBackend (existing)
    |                                       +-- ObjectDetectionBackend (existing)
    +-- DepthCameraInterface (NEW)          |
         +-- AzureKinectCamera              +-- DepthCameraDetectionBackend (NEW)
         +-- KinectV2Camera                      |
         +-- KinectV1Camera                      +-- KinectDetectionBackend
```

---

## New File Structure

```
ams/
+-- depth_camera/
|   +-- __init__.py
|   +-- interface.py           # DepthCameraInterface abstract base
|   +-- azure_kinect.py        # Azure Kinect (pyk4a)
|   +-- kinect_v2.py           # Kinect v2 (libfreenect2)
|   +-- kinect_v1.py           # Kinect v1 (libfreenect)
|
+-- depth_detection/
    +-- __init__.py
    +-- base.py                # DepthCameraDetectionBackend abstract base
    +-- kinect_backend.py      # KinectDetectionBackend concrete impl

models/
+-- primitives.py              # Add Point3D
+-- calibration.py             # Add Plane3D, DepthCalibrationData
+-- depth.py                   # SkeletonJoint, SkeletonEvent, BodyOcclusionEvent

calibration/
+-- depth_calibration.py       # Target plane calibration
```

---

## Key Interfaces

### DepthCameraInterface (extends CameraInterface)

```python
class CameraIntrinsics(NamedTuple):
    """Camera intrinsic parameters for 3D projection."""
    fx: float  # Focal length X
    fy: float  # Focal length Y
    cx: float  # Principal point X
    cy: float  # Principal point Y
    width: int
    height: int


class DepthCameraInterface(CameraInterface):
    """Extended camera interface with depth capture support."""

    @abstractmethod
    def capture_depth_frame(self) -> np.ndarray:
        """Return uint16 depth in millimeters, shape (h, w)."""

    @abstractmethod
    def capture_aligned_frames(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return (BGR, depth) aligned to same coordinate system."""

    @abstractmethod
    def get_depth_resolution(self) -> Tuple[int, int]: ...

    @abstractmethod
    def get_color_intrinsics(self) -> CameraIntrinsics: ...

    @abstractmethod
    def get_depth_intrinsics(self) -> CameraIntrinsics: ...

    @abstractmethod
    def supports_skeleton_tracking(self) -> bool: ...

    @abstractmethod
    def get_skeleton_data(self) -> Optional[SkeletonFrame]: ...

    def depth_to_world(self, u: int, v: int, depth_mm: int) -> Tuple[float, float, float]:
        """Convert pixel + depth to 3D world coordinates (meters)."""
        intrinsics = self.get_depth_intrinsics()
        z = depth_mm / 1000.0
        x = (u - intrinsics.cx) * z / intrinsics.fx
        y = (v - intrinsics.cy) * z / intrinsics.fy
        return (x, y, z)
```

### DepthCameraDetectionBackend (extends DetectionBackend)

```python
class DepthDetectionMode(Enum):
    DEPTH_FILTERED_IMPACTS = auto()  # Filter to target surface
    BODY_OCCLUSION = auto()          # Detect body blocking projection
    SKELETON_TRACKING = auto()        # Track skeleton joints


class DepthCameraDetectionBackend(DetectionBackend):
    """Abstract base class for depth-aware detection backends."""

    def __init__(
        self,
        camera: DepthCameraInterface,
        display_width: int,
        display_height: int,
        detection_modes: List[DepthDetectionMode] = None
    ):
        super().__init__(display_width, display_height)
        self.camera = camera
        self.detection_modes = detection_modes or [DepthDetectionMode.DEPTH_FILTERED_IMPACTS]
        self._target_plane: Optional[Plane3D] = None
        self._plane_tolerance_mm: float = 50.0

    @abstractmethod
    def set_target_plane(self, plane: Plane3D) -> None:
        """Set the target surface plane for depth filtering."""

    @abstractmethod
    def set_projected_pattern(self, pattern: np.ndarray) -> None:
        """Set current projected pattern for occlusion detection."""

    @abstractmethod
    def get_occlusion_events(self) -> List[BodyOcclusionEvent]: ...

    @abstractmethod
    def get_skeleton_events(self) -> List[SkeletonEvent]: ...

    def is_depth_calibrated(self) -> bool:
        return self._target_plane is not None
```

---

## New Data Models

### models/primitives.py additions

```python
class Point3D(BaseModel):
    """3D point in world coordinates (meters)."""
    x: float
    y: float
    z: float

    class Config:
        frozen = True
```

### models/calibration.py additions

```python
class Plane3D(BaseModel):
    """3D plane equation: ax + by + cz + d = 0"""
    a: float  # Normal x component
    b: float  # Normal y component
    c: float  # Normal z component
    d: float  # Distance from origin

    def distance_to_point(self, point: Point3D) -> float:
        """Calculate signed distance from point to plane."""
        numerator = abs(self.a * point.x + self.b * point.y + self.c * point.z + self.d)
        denominator = math.sqrt(self.a**2 + self.b**2 + self.c**2)
        return numerator / denominator
```

### models/depth.py (new file)

```python
class SkeletonJoint(BaseModel):
    """Single skeleton joint position."""
    joint_type: str  # "HEAD", "LEFT_HAND", "RIGHT_FOOT", etc.
    position_3d: Point3D
    position_2d: Tuple[float, float]  # normalized game coords
    confidence: float = Field(ge=0, le=1)


class SkeletonEvent(BaseModel):
    """Skeleton tracking event with all joints for a body."""
    timestamp: float
    body_id: int
    joints: Dict[str, SkeletonJoint]
    is_tracked: bool = True


class BodyOcclusionEvent(BaseModel):
    """Event when body occludes projected pattern."""
    timestamp: float
    occluded_regions: List[Tuple[float, float, float, float]]  # (x, y, w, h) normalized
    body_id: Optional[int] = None
```

---

## Detection Mode Data Flows

### 1. Depth-Filtered Impacts

```
KinectCamera.capture_aligned_frames()
    -> RGB + Depth
    -> Detect objects in RGB (existing ColorBlobDetector)
    -> For each detection: sample depth -> convert to 3D
    -> Filter: keep only if within plane_tolerance of target_plane
    -> Transform to normalized game coords
    -> Return PlaneHitEvent
```

### 2. Body Occlusion

```
Game provides: set_projected_pattern(current_frame)
    -> Backend computes expected camera view via inverse homography
    -> Capture actual RGB+Depth
    -> Diff actual vs expected (where body blocks projection)
    -> Return BodyOcclusionEvent with occluded regions
```

### 3. Skeleton Tracking

```
KinectCamera.get_skeleton_data()
    -> SDK provides 3D joint positions
    -> Project each joint to 2D game coordinates
    -> Return SkeletonEvent with joint dictionary
```

---

## 3D Calibration: Target Plane

Extend existing ArUco calibration to define the target surface plane:

1. During ArUco marker detection, sample depth at each marker corner
2. Convert 2D + depth -> 3D world coordinates using intrinsics
3. Fit plane to 3D points using SVD (least squares)
4. Save plane equation alongside homography in `calibration.json`

```python
# calibration/depth_calibration.py
class DepthCalibrationManager:
    def calibrate_target_plane(self, camera: DepthCameraInterface) -> Plane3D:
        rgb, depth = camera.capture_aligned_frames()
        markers = detect_aruco_markers(rgb)

        points_3d = []
        for marker in markers:
            for corner in marker.corners:
                d = depth[int(corner.y), int(corner.x)]
                if d > 0:
                    points_3d.append(camera.depth_to_world(corner.x, corner.y, d))

        return fit_plane_svd(points_3d)

    def fit_plane_svd(self, points: List[Tuple[float, float, float]]) -> Plane3D:
        """Fit plane to 3D points using SVD."""
        import numpy as np
        pts = np.array(points)
        centroid = pts.mean(axis=0)
        centered = pts - centroid
        _, _, vh = np.linalg.svd(centered)
        normal = vh[-1]  # Last row = plane normal
        d = -np.dot(normal, centroid)
        return Plane3D(a=normal[0], b=normal[1], c=normal[2], d=d)
```

---

## Integration: ams_game.py

### New Command Line Arguments

```python
parser.add_argument(
    '--kinect-type',
    choices=['azure', 'v2', 'v1'],
    default='azure',
    help='Kinect hardware generation'
)
parser.add_argument(
    '--enable-skeleton',
    action='store_true',
    help='Enable skeleton tracking (Azure Kinect, Kinect v2 only)'
)
parser.add_argument(
    '--enable-occlusion',
    action='store_true',
    help='Enable body occlusion detection'
)
parser.add_argument(
    '--depth-tolerance',
    type=float,
    default=50.0,
    help='Depth tolerance in mm for surface filtering'
)
```

### Backend Creation

```python
elif args.backend == 'kinect':
    from ams.depth_camera import AzureKinectCamera, KinectV2Camera, KinectV1Camera
    from ams.depth_detection import KinectDetectionBackend, DepthDetectionMode

    if args.kinect_type == 'azure':
        camera = AzureKinectCamera(enable_body_tracking=args.enable_skeleton)
    elif args.kinect_type == 'v2':
        camera = KinectV2Camera()
    else:
        camera = KinectV1Camera()

    modes = [DepthDetectionMode.DEPTH_FILTERED_IMPACTS]
    if args.enable_occlusion:
        modes.append(DepthDetectionMode.BODY_OCCLUSION)
    if args.enable_skeleton:
        modes.append(DepthDetectionMode.SKELETON_TRACKING)

    detection_backend = KinectDetectionBackend(
        camera=camera,
        calibration_manager=calibration_manager,
        depth_calibration_manager=depth_calibration_manager,
        display_width=DISPLAY_WIDTH,
        display_height=DISPLAY_HEIGHT,
        detection_modes=modes,
        plane_tolerance_mm=args.depth_tolerance
    )
```

---

## Implementation Phases

### Phase 1: Foundation
1. Add `Point3D`, `Plane3D`, `CameraIntrinsics` to models
2. Create `ams/depth_camera/interface.py` with `DepthCameraInterface`
3. Implement `KinectV1Camera` using libfreenect (prioritized - hardware available)

### Phase 2: Core Detection
4. Create `ams/depth_detection/base.py` with `DepthCameraDetectionBackend`
5. Implement `KinectDetectionBackend` with `DEPTH_FILTERED_IMPACTS` mode
6. Create `calibration/depth_calibration.py` for plane calibration

### Phase 3: Integration
7. Add `--backend kinect` to `ams_game.py`
8. Test end-to-end with simple_targets game using Kinect v1

### Phase 4: Body Occlusion Mode
9. Implement `BODY_OCCLUSION` mode + `BodyOcclusionEvent`
10. Test with laser maze prototype

### Phase 5: Additional Hardware (future)
11. Implement `KinectV2Camera` (libfreenect2 or pykinect2)
12. Implement `AzureKinectCamera` (pyk4a) - includes skeleton tracking

### Phase 6: Skeleton Tracking (requires v2/Azure)
13. Implement `SKELETON_TRACKING` mode + `SkeletonEvent`
14. Note: Kinect v1 has limited skeleton support via libfreenect

### Phase 7: Polish
15. Debug visualization (depth overlay, plane visualization)
16. Documentation updates to CLAUDE.md and guides

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `models/primitives.py` | Add `Point3D` |
| `models/calibration.py` | Add `Plane3D`, `CameraIntrinsics`, `DepthCalibrationData` |
| `models/depth.py` | **Create** - skeleton/occlusion event models |
| `ams/depth_camera/__init__.py` | **Create** - package exports |
| `ams/depth_camera/interface.py` | **Create** - `DepthCameraInterface` |
| `ams/depth_camera/azure_kinect.py` | **Create** - Azure Kinect impl |
| `ams/depth_camera/kinect_v2.py` | **Create** - Kinect v2 impl |
| `ams/depth_camera/kinect_v1.py` | **Create** - Kinect v1 impl |
| `ams/depth_detection/__init__.py` | **Create** - package exports |
| `ams/depth_detection/base.py` | **Create** - `DepthCameraDetectionBackend` |
| `ams/depth_detection/kinect_backend.py` | **Create** - `KinectDetectionBackend` |
| `calibration/depth_calibration.py` | **Create** - plane calibration |
| `ams_game.py` | Add kinect backend selection and args |
| `CLAUDE.md` | Document new backend |

---

## Graceful Degradation

| Situation | Behavior |
|-----------|----------|
| No plane calibration | Use full depth range (no filtering) |
| Depth sensor failure | Fall back to RGB-only detection |
| No skeleton SDK | Return empty skeleton events |
| Kinect disconnected | Clear error message, don't crash |
| Body tracking unavailable | Log warning, disable skeleton mode |

---

## SDK Dependencies

| Kinect Type | Python Package | Notes |
|-------------|----------------|-------|
| **Kinect v1** | `freenect` | **Priority** - hardware available |
| Kinect v2 | `pykinect2` or `pylibfreenect2` | Windows-focused or cross-platform |
| Azure Kinect | `pyk4a` | Best supported, includes body tracking |

Install Kinect v1 dependencies:
```bash
# macOS
brew install libfreenect
pip install freenect

# Ubuntu/Debian
sudo apt-get install libfreenect-dev
pip install freenect

# From source (if pip fails)
git clone https://github.com/OpenKinect/libfreenect
cd libfreenect && mkdir build && cd build
cmake .. && make && sudo make install
pip install freenect
```

---

## Kinect v1 Specifics

### Hardware Capabilities
- **RGB Camera**: 640x480 @ 30fps (can do 1280x1024 @ 15fps)
- **Depth Sensor**: 640x480 @ 30fps, range 0.8m - 4.0m
- **IR Projector**: Structured light pattern
- **Skeleton Tracking**: Limited (requires separate processing, not built-in SDK like v2/Azure)

### libfreenect API

```python
import freenect
import numpy as np

# Get RGB frame (returns BGR)
def get_rgb():
    rgb, _ = freenect.sync_get_video()
    return rgb[:, :, ::-1]  # RGB to BGR for OpenCV

# Get depth frame (11-bit, 0-2047 raw values)
def get_depth():
    depth, _ = freenect.sync_get_depth()
    return depth  # uint16, raw disparity values

# Convert raw depth to millimeters (approximate)
def raw_to_mm(raw_depth):
    # Kinect v1 uses structured light, not ToF
    # This is an approximation formula
    return 1000.0 / (raw_depth * -0.0030711016 + 3.3309495161)
```

### Kinect v1 Intrinsics (typical values)

```python
# RGB camera intrinsics (640x480)
RGB_INTRINSICS = CameraIntrinsics(
    fx=525.0,
    fy=525.0,
    cx=319.5,
    cy=239.5,
    width=640,
    height=480
)

# Depth sensor intrinsics (640x480)
DEPTH_INTRINSICS = CameraIntrinsics(
    fx=580.0,
    fy=580.0,
    cx=314.0,
    cy=235.0,
    width=640,
    height=480
)
```

### Depth-RGB Alignment

Kinect v1 RGB and depth sensors are offset, requiring alignment:

```python
def align_depth_to_rgb(depth_frame, depth_intrinsics, rgb_intrinsics):
    """Transform depth frame to RGB camera coordinate system."""
    # This requires the extrinsic calibration between sensors
    # libfreenect provides registration functions:
    # freenect.sync_get_depth(format=freenect.DEPTH_REGISTERED)
    pass
```

### Limitations vs Newer Kinects
- No built-in skeleton tracking SDK (OpenNI/NiTE required separately)
- Lower depth resolution and accuracy
- Shorter range (0.8m - 4.0m vs 0.5m - 5.5m for v2)
- More susceptible to IR interference (sunlight)
- Structured light vs ToF means depth holes at edges

### Recommended Initial Implementation

For Kinect v1, focus on:
1. **DEPTH_FILTERED_IMPACTS** - works well with available hardware
2. **BODY_OCCLUSION** - simple depth differencing, no skeleton needed
3. Skip skeleton tracking initially (requires extra dependencies)

```python
# Simplified KinectV1Camera implementation
class KinectV1Camera(DepthCameraInterface):
    def __init__(self, device_id: int = 0):
        import freenect
        self._ctx = freenect.init()
        self._dev = freenect.open_device(self._ctx, device_id)
        freenect.set_depth_mode(self._dev, freenect.DEPTH_11BIT)
        freenect.set_video_mode(self._dev, freenect.VIDEO_RGB)
        freenect.start_depth(self._dev)
        freenect.start_video(self._dev)

    def capture_frame(self) -> np.ndarray:
        rgb, _ = freenect.sync_get_video()
        return rgb[:, :, ::-1]  # RGB -> BGR

    def capture_depth_frame(self) -> np.ndarray:
        depth, _ = freenect.sync_get_depth()
        return self._raw_to_mm(depth)

    def _raw_to_mm(self, raw: np.ndarray) -> np.ndarray:
        # Convert 11-bit raw to millimeters
        with np.errstate(divide='ignore', invalid='ignore'):
            mm = 1000.0 / (raw * -0.0030711016 + 3.3309495161)
            mm[raw == 0] = 0  # Invalid depth
            mm[raw == 2047] = 0  # Max range (invalid)
        return mm.astype(np.uint16)

    def supports_skeleton_tracking(self) -> bool:
        return False  # Not without OpenNI/NiTE

    def get_skeleton_data(self):
        return None
```
