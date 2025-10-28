# Object Detection with AMS

Detect and track physical objects (nerf darts, arrows, balls) using computer vision and register impacts when they hit targets.

## Overview

The object detection backend uses:
- **Color blob detection** (HSV filtering) for tracking colored objects
- **Impact detection** (velocity-based) to register when objects hit and stop
- **ArUco calibration** for accurate camera-to-screen coordinate mapping
- **Pluggable detector API** for easy addition of new detection algorithms

## Quick Start

### Mouse Mode (Development/Testing)
```bash
python ams_demo.py --backend mouse
```

### Object Detection Mode (Nerf Darts)
```bash
# First run - calibrate with ArUco markers
python ams_demo.py --backend object --fullscreen --display 1

# Press 'C' to calibrate with ArUco markers
# Position camera to see all markers, press SPACE

# Subsequent runs - calibration auto-loads
python ams_demo.py --backend object --fullscreen --display 1
```

### Duck Hunt with Object Detection
```bash
python duckhunt_ams.py --backend object --fullscreen --display 1 --mode classic_archery
```

## How It Works

### 1. Color Blob Detection
Objects are detected by color using HSV (Hue, Saturation, Value) color space:

```python
from ams.object_detection import ColorBlobDetector, ColorBlobConfig

# Configure for orange/red nerf darts
config = ColorBlobConfig(
    hue_min=0,          # Red-orange hue (0-179)
    hue_max=15,
    saturation_min=100,  # Minimum color saturation (0-255)
    saturation_max=255,
    value_min=100,       # Minimum brightness (0-255)
    value_max=255,
    min_area=50,         # Minimum blob size in pixels
    max_area=2000,       # Maximum blob size
)

detector = ColorBlobDetector(config)
```

### 2. Object Tracking
Each detected object is tracked frame-to-frame to calculate velocity:

- **Position**: Center point of the detected blob
- **Velocity**: Change in position over time (pixels/second)
- **Area**: Size of the detected blob
- **Bounding box**: Rectangle around the object

### 3. Impact Detection
An impact is registered when:

1. **Object slows down**: Velocity drops below threshold (default: 15 pixels/sec)
2. **Stays stationary**: Remains slow for minimum duration (default: 150ms)
3. **Within bounds**: Position is within game area after calibration

```
Moving → Slowing → Stationary (150ms) → IMPACT!
```

### 4. Coordinate Transformation
Using ArUco calibration, object positions are transformed:

```
Camera Coordinates → Projector Coordinates → Game Coordinates [0,1]
```

## Configuration

### HSV Color Tuning

Different colored objects require different HSV ranges:

| Object Color | Hue Min | Hue Max | Example |
|--------------|---------|---------|---------|
| Red/Orange | 0 | 15 | Orange nerf darts |
| Yellow | 20 | 40 | Yellow balls |
| Green | 40 | 80 | Green arrows |
| Blue | 100 | 130 | Blue markers |

**Tip**: Use the debug view (press 'D') to see the HSV mask and tune values in real-time.

### Impact Detection Parameters

```python
ObjectDetectionBackend(
    camera=camera,
    detector=detector,
    impact_velocity_threshold=15.0,  # Adjust for faster/slower objects
    impact_duration=0.15,             # Adjust for more/less sensitive detection
)
```

| Parameter | Description | Suggested Range |
|-----------|-------------|-----------------|
| `impact_velocity_threshold` | Speed below which object is "stopped" (px/s) | 10-30 |
| `impact_duration` | How long object must be stopped (seconds) | 0.1-0.3 |

## Controls

### Object Detection Mode
- **Throw/shoot object**: Register hit when it impacts target
- **D**: Toggle debug visualization
- **C**: Recalibrate ArUco markers
- **ESC**: Quit

### Debug Visualization

Press **D** to see:
- **Left panel**: Detection view
  - Green boxes: Detected objects
  - Blue arrows: Velocity vectors
  - Orange circles: Stationary objects
  - Red circles: Impact events
  - White overlays: Target positions (from game)
- **Right panel**: HSV mask
  - White: Pixels matching color filter
  - Black: Filtered out

## Calibration Workflow

### 1. Setup
```bash
python ams_demo.py --backend object --fullscreen --display 1
```

### 2. Calibrate (First Run)
- ArUco pattern displays on projector
- Camera preview window shows marker detection
- Position camera until all 16 markers detected
- Press SPACE to capture
- Calibration saves to `calibration.json`

### 3. Tune Color Detection
Press **D** to see debug view:
- Throw your object through the camera view
- Check if it appears white in the mask (right panel)
- If not detected, adjust HSV ranges in code
- Rerun the program to test

### 4. Test Impact Detection
- Throw/shoot object at targets
- Object should be tracked (green box + blue arrow)
- When it hits and stops, red circle appears
- Game should register the hit

### 5. Play!
Once calibrated and tuned:
```bash
python duckhunt_ams.py --backend object --fullscreen --display 1
```

## Troubleshooting

### "No objects detected"
**Solution**: Adjust HSV ranges
- Press **D** for debug view
- Look at the mask (right panel)
- If your object isn't white:
  - Increase `value_min` if too dark
  - Decrease `saturation_min` if color too faint
  - Adjust `hue_min`/`hue_max` for different color
- Edit ranges in `ams_demo.py` or `duckhunt_ams.py`

### "Objects detected everywhere"
**Solution**: Narrow color range or increase area filter
- Too much showing as white in mask
- Increase `saturation_min` and `value_min`
- Narrow `hue_min`/`hue_max` range
- Increase `min_area` to ignore small blobs

### "Objects detected but no impacts"
**Possible causes**:
1. **Object moving too fast**
   - Lower `impact_velocity_threshold` (e.g., 10 instead of 15)
2. **Object bouncing off**
   - Decrease `impact_duration` (e.g., 0.1 instead of 0.15)
3. **Calibration misaligned**
   - Check debug view: white circles should overlay blue targets
   - If misaligned: Press 'C' to recalibrate
4. **Object not stopping**
   - Try softer material (nerf darts work great)
   - Ensure objects stick/stop at impact point

### "Impacts registering randomly"
**Solution**: Tighten detection thresholds
- Increase `impact_velocity_threshold` (e.g., 20 instead of 15)
- Increase `impact_duration` (e.g., 0.2 instead of 0.15)
- Increase `min_area` to ignore noise

## Adding New Detection Algorithms

The system is designed for easy extension:

### 1. Create Detector Class

```python
from ams.object_detection.base import ObjectDetector, DetectedObject
import numpy as np

class MyCustomDetector(ObjectDetector):
    def detect(self, frame: np.ndarray, timestamp: float) -> List[DetectedObject]:
        # Your detection algorithm here
        detections = []
        # ... find objects ...
        return detections

    def get_debug_frame(self) -> Optional[np.ndarray]:
        return self.debug_frame

    def set_debug_mode(self, enabled: bool) -> None:
        self.debug_mode = enabled

    def configure(self, **kwargs) -> None:
        # Handle dynamic configuration
        pass
```

### 2. Use in Backend

```python
from ams.object_detection_backend import ObjectDetectionBackend
from my_detector import MyCustomDetector

detector = MyCustomDetector()
backend = ObjectDetectionBackend(
    camera=camera,
    detector=detector,  # Your custom detector
    calibration_manager=calibration_manager
)
```

### Example: Shape-Based Detection

```python
class ShapeDetector(ObjectDetector):
    """Detect arrows or darts by shape."""

    def detect(self, frame, timestamp):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        for contour in contours:
            # Check if shape looks like arrow
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)

            if len(approx) == 4:  # Four-sided shape
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = float(w) / h

                if 2.0 < aspect_ratio < 5.0:  # Long and thin
                    # Detected arrow-like shape!
                    detections.append(...)

        return detections
```

## Architecture

```
User throws nerf dart
    ↓
Camera captures frame
    ↓
ColorBlobDetector (HSV filtering)
    ↓
Object tracking (velocity calculation)
    ↓
Impact detection (velocity threshold + duration)
    ↓
Coordinate transformation (ArUco calibration)
    ↓
Hit event sent to game
    ↓
Score!
```

## Best Practices

1. **Lighting**: Consistent, bright lighting works best for color detection
2. **Background**: Plain, contrasting background improves detection
3. **Object color**: Choose colors not present in background
4. **Calibration**: Recalibrate if you move camera or projector
5. **Testing**: Start with mouse mode to verify game logic works
6. **Tuning**: Use debug view to tune HSV ranges before playing

## Next Steps

- Experiment with different colored objects
- Adjust impact thresholds for your throwing speed
- Try different game modes (`classic_archery`, `classic_ducks`, `classic_linear`)
- Create custom detectors for specific object shapes
