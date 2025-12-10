"""
Duck sprite management for Duck Hunt game.

Loads and manages sprite animations from the sprites.png sprite sheet.
"""

import os
from typing import Dict, List, Tuple, Optional
from enum import Enum
import pygame


class DuckColor(Enum):
    """Duck color variants available in the sprite sheet."""
    GREEN = 0
    BLUE = 1
    RED = 2


class DuckDirection(Enum):
    """Movement direction for selecting appropriate sprite animation."""
    UP_LEFT = "up_left"      # Diagonal up-left
    UP_RIGHT = "up_right"    # Diagonal up-right
    LEFT = "left"            # Horizontal left
    RIGHT = "right"          # Horizontal right
    UP = "up"                # Straight up
    HIT = "hit"              # Hit/dead pose (stationary)
    FALLING = "falling"      # Falling down


class DuckSprites:
    """Manages duck sprite animations from the sprite sheet.

    The sprite sheet (assets/sprites.png) contains:
    - Rows 0-1: Dog sprites (not used here)
    - Row 2: Green duck animations
    - Row 3: Blue duck animations
    - Row 4: Red duck animations

    Each duck row contains (left to right):
    - 3 frames level flight (flying RIGHT)
    - 3 frames diagonal up-right
    - 1 frame shot/hit (still)
    - 4 frames falling

    LEFT and UP_LEFT sprites are created by flipping the RIGHT/UP_RIGHT frames.
    """

    # Sprite sheet layout constants (measured from sprite sheet)
    DUCK_START_Y = 126  # Y position where duck rows start
    DUCK_ROW_HEIGHT = 42  # Height of each duck row
    DUCK_SPRITE_HEIGHT = 41  # Height of each duck sprite

    # Frame positions within each row: (x_offset, width) - 11 frames total
    # Each sprite has variable width
    FRAME_POSITIONS = [
        # Level flight RIGHT (3 frames) - ~35px wide each
        (7, 37), (48, 37), (88, 37),
        # Diagonal UP_RIGHT (3 frames) - ~35px wide each
        (134, 35), (168, 35), (202, 35),
        # Shot/Hit still (1 frame) - narrower ~24px
        (236, 35),
        # Falling (4 frames) - variable widths
        (279, 22), (302, 22), (327, 22), (350, 22),
    ]

    # Animation speed (frames per second)
    ANIMATION_FPS = 1.5

    def __init__(self, assets_dir: Optional[str] = None):
        """Initialize sprite manager and load sprites.

        Args:
            assets_dir: Path to assets directory. If None, uses default location.
        """
        if assets_dir is None:
            # Default to assets directory relative to this file
            assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

        self._sprites: Dict[DuckColor, Dict[DuckDirection, List[pygame.Surface]]] = {}
        self._loaded = False
        self._assets_dir = assets_dir
        self._animation_time = 0.0

    def load(self) -> bool:
        """Load sprites from sprite sheet.

        Returns:
            True if sprites loaded successfully, False otherwise.
        """
        if self._loaded:
            return True

        sprite_path = os.path.join(self._assets_dir, "sprites.png")
        if not os.path.exists(sprite_path):
            print(f"Warning: Sprite sheet not found at {sprite_path}")
            return False

        try:
            sheet = pygame.image.load(sprite_path).convert()
        except pygame.error as e:
            print(f"Warning: Could not load sprite sheet: {e}")
            return False

        # The green background color to make transparent
        # Using convert() (not convert_alpha()) so colorkey works properly
        transparent_color = (159, 227, 163)  # Light green background (sampled from sprite sheet)

        # Extract sprites for each duck color
        for color_idx, color in enumerate(DuckColor):
            row_y = self.DUCK_START_Y + (color_idx * self.DUCK_ROW_HEIGHT)
            self._sprites[color] = self._extract_duck_row(sheet, row_y, transparent_color)

        self._loaded = True
        return True

    def _extract_duck_row(
        self,
        sheet: pygame.Surface,
        row_y: int,
        transparent_color: Tuple[int, int, int]
    ) -> Dict[DuckDirection, List[pygame.Surface]]:
        """Extract all animation frames for a single duck row.

        Args:
            sheet: The full sprite sheet surface
            row_y: Y position of this duck's row
            transparent_color: RGB color to make transparent

        Returns:
            Dictionary mapping directions to lists of animation frames
        """
        frames: Dict[DuckDirection, List[pygame.Surface]] = {
            DuckDirection.UP_LEFT: [],
            DuckDirection.LEFT: [],
            DuckDirection.UP_RIGHT: [],
            DuckDirection.RIGHT: [],
            DuckDirection.UP: [],
            DuckDirection.HIT: [],
            DuckDirection.FALLING: [],
        }

        # Extract each frame from the row
        for i, (frame_x, frame_width) in enumerate(self.FRAME_POSITIONS):
            # Create subsurface for this frame using variable width
            rect = pygame.Rect(
                frame_x,
                row_y,
                frame_width,
                self.DUCK_SPRITE_HEIGHT
            )

            # Ensure we don't go out of bounds
            if rect.right > sheet.get_width() or rect.bottom > sheet.get_height():
                continue

            frame = sheet.subsurface(rect).copy()

            # Make background transparent
            frame.set_colorkey(transparent_color)

            # Assign to appropriate direction based on sprite sheet layout:
            # 0-2: Level flight RIGHT, 3-5: Diagonal UP_RIGHT, 6: HIT, 7-10: FALLING
            if i < 3:
                # Level flight frames (flying RIGHT)
                frames[DuckDirection.RIGHT].append(frame)
            elif i < 6:
                # Diagonal up-right frames
                frames[DuckDirection.UP_RIGHT].append(frame)
            elif i == 6:
                # Shot/hit still frame
                frames[DuckDirection.HIT].append(frame)
            else:
                # Falling frames (4 frames)
                frames[DuckDirection.FALLING].append(frame)

        # Create LEFT frames by flipping RIGHT frames horizontally
        for frame in frames[DuckDirection.RIGHT]:
            flipped = pygame.transform.flip(frame, True, False)
            frames[DuckDirection.LEFT].append(flipped)

        # Create UP_LEFT frames by flipping UP_RIGHT frames horizontally
        for frame in frames[DuckDirection.UP_RIGHT]:
            flipped = pygame.transform.flip(frame, True, False)
            frames[DuckDirection.UP_LEFT].append(flipped)

        # Create UP frames from UP_RIGHT (for steep upward flight)
        for frame in frames[DuckDirection.UP_RIGHT]:
            frames[DuckDirection.UP].append(frame)

        return frames

    def update(self, dt: float) -> None:
        """Update animation timer.

        Args:
            dt: Time delta in seconds
        """
        self._animation_time += dt

    def get_frame(
        self,
        color: DuckColor,
        direction: DuckDirection,
        scale: float = 1.0
    ) -> Optional[pygame.Surface]:
        """Get the current animation frame for a duck.

        Args:
            color: Duck color variant
            direction: Movement direction
            scale: Scale factor for the sprite (1.0 = original size)

        Returns:
            The current animation frame surface, or None if not loaded
        """
        if not self._loaded:
            return None

        if color not in self._sprites:
            return None

        direction_frames = self._sprites[color].get(direction, [])
        if not direction_frames:
            return None

        # Calculate which frame to show based on animation time
        frame_duration = 1.0 / self.ANIMATION_FPS
        total_frames = len(direction_frames)
        frame_index = int(self._animation_time / frame_duration) % total_frames

        frame = direction_frames[frame_index]

        # Scale if needed
        if scale != 1.0:
            new_width = int(frame.get_width() * scale)
            new_height = int(frame.get_height() * scale)
            colorkey = frame.get_colorkey()
            frame = pygame.transform.scale(frame, (new_width, new_height))
            # Re-apply colorkey after scaling (scale doesn't preserve it)
            if colorkey:
                frame.set_colorkey(colorkey)

        return frame

    def get_direction_from_velocity(self, vx: float, vy: float) -> DuckDirection:
        """Determine sprite direction from velocity vector.

        Uses angle-based detection:
        - Steep angles (> 60 degrees from horizontal) → UP sprite
        - Diagonal angles (30-60 degrees) → UP_LEFT or UP_RIGHT
        - Shallow angles (< 30 degrees) → LEFT or RIGHT (horizontal)

        Args:
            vx: X component of velocity
            vy: Y component of velocity (negative = up in pygame coords)

        Returns:
            Appropriate DuckDirection for the velocity
        """
        import math

        # Handle near-zero velocity
        speed = math.sqrt(vx * vx + vy * vy)
        if speed < 5:
            return DuckDirection.RIGHT  # Default for stationary

        # Calculate angle from horizontal (0 = right, 90 = up, -90 = down)
        # In pygame, negative y is up, so we negate vy for standard angle calc
        angle = math.degrees(math.atan2(-vy, abs(vx)))

        # Determine if going left or right
        going_left = vx < 0
        going_down = vy > 0

        # If going down significantly, it's falling
        if going_down and angle < -30:
            return DuckDirection.FALLING

        # Steep upward angle (> 60 degrees from horizontal) → UP sprite
        if angle > 60:
            return DuckDirection.UP

        # Diagonal angle (30-60 degrees)
        if angle > 30:
            return DuckDirection.UP_LEFT if going_left else DuckDirection.UP_RIGHT

        # Shallow angle (< 30 degrees) → horizontal sprite
        return DuckDirection.LEFT if going_left else DuckDirection.RIGHT

    @property
    def is_loaded(self) -> bool:
        """Check if sprites are loaded."""
        return self._loaded

    # Base sprite width for scaling calculations (flying sprites)
    DUCK_SPRITE_WIDTH = 35

    @property
    def sprite_size(self) -> Tuple[int, int]:
        """Get the base sprite size (width, height) for scaling."""
        return (self.DUCK_SPRITE_WIDTH, self.DUCK_SPRITE_HEIGHT)


# Global sprite manager instance
_duck_sprites: Optional[DuckSprites] = None


def get_duck_sprites() -> DuckSprites:
    """Get the global duck sprites manager.

    Creates and loads sprites on first call.

    Returns:
        The global DuckSprites instance
    """
    global _duck_sprites
    if _duck_sprites is None:
        _duck_sprites = DuckSprites()
        _duck_sprites.load()
    return _duck_sprites
