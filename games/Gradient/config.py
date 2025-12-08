"""
Configuration for Gradient Test Game.

Position-encoded gradient for CV pipeline validation.
"""

# Screen dimensions (will be overridden by actual screen size)
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# Colors
BACKGROUND_COLOR = (20, 20, 30)
TEXT_COLOR = (255, 255, 255)
HEADER_COLOR = (200, 200, 200)

# Marker colors based on error magnitude
MARKER_EXCELLENT = (50, 255, 50)    # Green - < 1% error
MARKER_GOOD = (150, 255, 50)        # Yellow-green - 1-2% error
MARKER_WARNING = (255, 200, 50)     # Yellow - 2-3% error
MARKER_BAD = (255, 100, 50)         # Orange - 3-5% error
MARKER_TERRIBLE = (255, 50, 50)     # Red - > 5% error

# Error thresholds (as percentage of screen diagonal)
ERROR_EXCELLENT = 0.01   # 1%
ERROR_GOOD = 0.02        # 2%
ERROR_WARNING = 0.03     # 3%
ERROR_BAD = 0.05         # 5%

# Marker appearance
MARKER_RADIUS = 8
MARKER_INNER_RADIUS = 3
ERROR_LINE_WIDTH = 2

# UI Layout
HEADER_HEIGHT = 80
STATS_WIDTH = 250
MARGIN = 20

# Gradient area (computed from screen size minus header/margins)
GRADIENT_MARGIN = 10
