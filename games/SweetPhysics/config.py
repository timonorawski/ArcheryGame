"""
Configuration for Sweet Physics game.
"""

# Screen dimensions (will be overridden by actual screen size)
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# Colors
BACKGROUND_COLOR = (25, 30, 45)
TEXT_COLOR = (255, 255, 255)
HEADER_COLOR = (200, 200, 200)

# Physics constants
GRAVITY = (0, 980)  # pixels/sec^2 (downward)
PHYSICS_STEPS = 10  # substeps per frame for stability
AIR_RESISTANCE = 0.995  # velocity damping

# Candy (payload) settings
CANDY_RADIUS = 20
CANDY_MASS = 1.0
CANDY_ELASTICITY = 0.3
CANDY_FRICTION = 0.5
CANDY_COLOR = (255, 100, 150)  # Pink candy
CANDY_OUTLINE = (200, 50, 100)

# Rope settings
ROPE_SEGMENT_LENGTH = 15
ROPE_SEGMENT_MASS = 0.05
ROPE_STIFFNESS = 5000  # Spring stiffness for damped spring joints
ROPE_DAMPING = 100
ROPE_COLOR = (139, 90, 43)  # Brown rope
ROPE_WIDTH = 3
ROPE_HIT_RADIUS = 15  # How close a hit needs to be to cut

# Goal settings
GOAL_RADIUS = 50
GOAL_COLOR = (100, 200, 100)
GOAL_OUTLINE = (50, 150, 50)
GOAL_PULSE_SPEED = 2.0

# Star settings
STAR_RADIUS = 18
STAR_COLOR = (255, 215, 0)  # Gold
STAR_OUTLINE = (200, 165, 0)
STAR_COLLECTED_ALPHA = 100

# Bubble settings
BUBBLE_RADIUS = 40
BUBBLE_COLOR = (100, 200, 255, 100)  # Translucent blue
BUBBLE_OUTLINE = (150, 220, 255)
BUBBLE_FLOAT_FORCE = -400  # Upward force

# Air cushion settings
AIR_CUSHION_FORCE = 600
AIR_CUSHION_COLOR = (200, 200, 255)

# Platform settings
PLATFORM_COLOR = (80, 80, 100)
PLATFORM_OUTLINE = (100, 100, 120)

# Spike settings
SPIKE_COLOR = (200, 50, 50)

# UI Layout
HEADER_HEIGHT = 60
MARGIN = 20

# Level bounds (margin outside screen where candy is lost)
BOUNDS_MARGIN = 100

# Hit detection
HIT_RADIUS = 12  # Radius around click point for hit detection

# Animation
WIN_DELAY = 1.5  # Seconds to show win state before advancing
FAIL_DELAY = 1.0  # Seconds before retry prompt

# Collision types for Pymunk
COLLISION_CANDY = 1
COLLISION_GOAL = 2
COLLISION_STAR = 3
COLLISION_SPIKE = 4
COLLISION_WALL = 5
COLLISION_BUBBLE = 6
