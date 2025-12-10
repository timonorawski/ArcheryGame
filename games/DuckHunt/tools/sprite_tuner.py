#!/usr/bin/env python3
"""
Sprite Tuner - Visual tool for tuning sprite sheet extraction.

Controls:
  Arrow Keys: Nudge selected sprite (Left/Right/Up/Down)
  W/S: Increase/Decrease width
  Tab: Select next sprite
  Shift+Tab: Select previous sprite
  R: Select next row (duck color)
  C: Copy current FRAME_POSITIONS to clipboard (printed to console)
  Q/Escape: Quit

Shows all sprites in boxes with their current (x, width) values.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from typing import List, Tuple

# Sprite sheet layout - edit these values!
DUCK_START_Y = 124
DUCK_ROW_HEIGHT = 44
DUCK_SPRITE_HEIGHT = 41

# Frame positions: (x_offset, width) for each of 11 frames
FRAME_POSITIONS: List[Tuple[int, int]] = [
    # Level flight RIGHT (3 frames)
    (2, 37), (46, 37), (85, 37),
    # Diagonal UP_RIGHT (3 frames)
    (111, 35), (148, 35), (185, 35),
    # Shot/Hit still (1 frame)
    (222, 24),
    # Falling (4 frames)
    (248, 17), (267, 18), (287, 17), (306, 17),
]

FRAME_LABELS = [
    "Fly R 1", "Fly R 2", "Fly R 3",
    "Diag 1", "Diag 2", "Diag 3",
    "Hit",
    "Fall 1", "Fall 2", "Fall 3", "Fall 4",
]

ROW_LABELS = ["Green", "Blue", "Red"]


class SpriteTuner:
    def __init__(self):
        pygame.init()

        # Window setup
        self.screen_width = 1200
        self.screen_height = 800
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Sprite Tuner - Arrow keys to nudge, W/S for width, Tab to switch")

        # Load sprite sheet
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        sprite_path = os.path.join(assets_dir, "sprites.png")
        self.sheet = pygame.image.load(sprite_path).convert_alpha()

        # Transparent color
        self.transparent_color = (172, 220, 94)

        # Selection state
        self.selected_frame = 0
        self.selected_row = 0  # 0=Green, 1=Blue, 2=Red

        # Copy of frame positions for editing
        self.frame_positions = list(FRAME_POSITIONS)

        # Font
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)

        # Colors
        self.bg_color = (40, 40, 50)
        self.box_color = (80, 80, 100)
        self.selected_color = (255, 200, 50)
        self.text_color = (220, 220, 220)

    def get_row_y(self, row: int) -> int:
        """Get Y position for a duck row."""
        return DUCK_START_Y + (row * DUCK_ROW_HEIGHT)

    def extract_sprite(self, frame_idx: int, row: int) -> pygame.Surface:
        """Extract a single sprite from the sheet."""
        x, width = self.frame_positions[frame_idx]
        y = self.get_row_y(row)

        # Clamp to sheet bounds
        x = max(0, min(x, self.sheet.get_width() - 1))
        width = max(1, min(width, self.sheet.get_width() - x))
        height = min(DUCK_SPRITE_HEIGHT, self.sheet.get_height() - y)

        if width <= 0 or height <= 0:
            return pygame.Surface((1, 1))

        rect = pygame.Rect(x, y, width, height)
        sprite = self.sheet.subsurface(rect).copy()
        sprite.set_colorkey(self.transparent_color)
        return sprite

    def draw(self):
        self.screen.fill(self.bg_color)

        # Draw title and instructions
        title = self.font.render("Sprite Tuner - Press C to copy positions, Q to quit", True, self.text_color)
        self.screen.blit(title, (20, 10))

        instructions = self.small_font.render(
            "Arrow Keys: nudge | W/S: width | Tab: next sprite | R: next row | Shift+Arrow: x10",
            True, (150, 150, 150)
        )
        self.screen.blit(instructions, (20, 35))

        # Layout: show sprites in a grid
        margin = 20
        box_padding = 10
        max_sprite_display_width = 80
        max_sprite_display_height = 80

        # Calculate box size
        box_width = max_sprite_display_width + box_padding * 2
        box_height = max_sprite_display_height + 60  # Extra space for labels

        start_y = 70

        # Draw each frame
        for i, (x, width) in enumerate(self.frame_positions):
            col = i % 6
            row_display = i // 6

            box_x = margin + col * (box_width + 10)
            box_y = start_y + row_display * (box_height + 10)

            # Draw box
            is_selected = (i == self.selected_frame)
            box_color = self.selected_color if is_selected else self.box_color
            pygame.draw.rect(self.screen, box_color, (box_x, box_y, box_width, box_height), 2 if not is_selected else 3)

            # Extract and draw sprite (scaled to fit)
            sprite = self.extract_sprite(i, self.selected_row)

            # Scale sprite to fit in display area
            scale = min(max_sprite_display_width / max(sprite.get_width(), 1),
                       max_sprite_display_height / max(sprite.get_height(), 1),
                       3.0)  # Max 3x zoom

            scaled_width = int(sprite.get_width() * scale)
            scaled_height = int(sprite.get_height() * scale)

            if scaled_width > 0 and scaled_height > 0:
                scaled_sprite = pygame.transform.scale(sprite, (scaled_width, scaled_height))

                # Center sprite in box
                sprite_x = box_x + (box_width - scaled_width) // 2
                sprite_y = box_y + box_padding + (max_sprite_display_height - scaled_height) // 2

                # Draw checkerboard background for transparency
                checker_rect = pygame.Rect(sprite_x - 2, sprite_y - 2, scaled_width + 4, scaled_height + 4)
                self._draw_checkerboard(checker_rect)

                self.screen.blit(scaled_sprite, (sprite_x, sprite_y))

            # Draw label
            label = self.small_font.render(FRAME_LABELS[i], True, self.text_color)
            label_x = box_x + (box_width - label.get_width()) // 2
            self.screen.blit(label, (label_x, box_y + box_height - 45))

            # Draw position info
            pos_text = f"x={x}, w={width}"
            pos_label = self.small_font.render(pos_text, True, (150, 200, 150) if is_selected else (120, 120, 120))
            pos_x = box_x + (box_width - pos_label.get_width()) // 2
            self.screen.blit(pos_label, (pos_x, box_y + box_height - 25))

        # Draw current row indicator
        row_text = f"Row: {ROW_LABELS[self.selected_row]} (Press R to change)"
        row_label = self.font.render(row_text, True, self.selected_color)
        self.screen.blit(row_label, (20, start_y + 2 * (box_height + 10) + 20))

        # Draw full sprite sheet preview with extraction boxes
        self._draw_sheet_preview(start_y + 2 * (box_height + 10) + 60)

        pygame.display.flip()

    def _draw_checkerboard(self, rect: pygame.Rect):
        """Draw a checkerboard pattern for transparency visualization."""
        checker_size = 4
        colors = [(60, 60, 60), (80, 80, 80)]
        for y in range(rect.top, rect.bottom, checker_size):
            for x in range(rect.left, rect.right, checker_size):
                color_idx = ((x - rect.left) // checker_size + (y - rect.top) // checker_size) % 2
                check_rect = pygame.Rect(x, y,
                                         min(checker_size, rect.right - x),
                                         min(checker_size, rect.bottom - y))
                pygame.draw.rect(self.screen, colors[color_idx], check_rect)

    def _draw_sheet_preview(self, start_y: int):
        """Draw a preview of the sprite sheet with extraction boxes."""
        # Scale factor for preview
        scale = 2.0

        # Get the relevant portion of the sheet
        preview_height = int(DUCK_ROW_HEIGHT * 3 * scale)
        preview_y = DUCK_START_Y

        # Create preview surface
        preview_rect = pygame.Rect(0, preview_y, self.sheet.get_width(), DUCK_ROW_HEIGHT * 3)
        if preview_rect.bottom > self.sheet.get_height():
            preview_rect.height = self.sheet.get_height() - preview_rect.top

        preview = self.sheet.subsurface(preview_rect).copy()
        scaled_preview = pygame.transform.scale(
            preview,
            (int(preview.get_width() * scale), int(preview.get_height() * scale))
        )

        # Draw preview
        preview_x = 20
        self.screen.blit(scaled_preview, (preview_x, start_y))

        # Draw extraction boxes on preview
        for i, (x, width) in enumerate(self.frame_positions):
            is_selected = (i == self.selected_frame)
            color = self.selected_color if is_selected else (100, 150, 255)

            # Draw box for current row
            box_x = preview_x + int(x * scale)
            box_y = start_y + int(self.selected_row * DUCK_ROW_HEIGHT * scale)
            box_w = int(width * scale)
            box_h = int(DUCK_SPRITE_HEIGHT * scale)

            pygame.draw.rect(self.screen, color, (box_x, box_y, box_w, box_h), 2 if is_selected else 1)

        # Draw row labels
        for i, label in enumerate(ROW_LABELS):
            label_y = start_y + int((i + 0.5) * DUCK_ROW_HEIGHT * scale) - 8
            text = self.small_font.render(label, True, self.text_color)
            self.screen.blit(text, (preview_x + int(self.sheet.get_width() * scale) + 10, label_y))

    def handle_input(self, event: pygame.event.Event) -> bool:
        """Handle input event. Returns False if should quit."""
        global DUCK_START_Y

        if event.type == pygame.QUIT:
            return False

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            shift = mods & pygame.KMOD_SHIFT
            step = 10 if shift else 1

            if event.key in (pygame.K_q, pygame.K_ESCAPE):
                return False

            elif event.key == pygame.K_TAB:
                if shift:
                    self.selected_frame = (self.selected_frame - 1) % len(self.frame_positions)
                else:
                    self.selected_frame = (self.selected_frame + 1) % len(self.frame_positions)

            elif event.key == pygame.K_r:
                self.selected_row = (self.selected_row + 1) % 3

            elif event.key == pygame.K_LEFT:
                x, w = self.frame_positions[self.selected_frame]
                self.frame_positions[self.selected_frame] = (max(0, x - step), w)

            elif event.key == pygame.K_RIGHT:
                x, w = self.frame_positions[self.selected_frame]
                self.frame_positions[self.selected_frame] = (x + step, w)

            elif event.key == pygame.K_UP:
                # Nudge Y - this changes DUCK_START_Y globally
                DUCK_START_Y = max(0, DUCK_START_Y - step)

            elif event.key == pygame.K_DOWN:
                DUCK_START_Y += step

            elif event.key == pygame.K_w:
                x, w = self.frame_positions[self.selected_frame]
                self.frame_positions[self.selected_frame] = (x, w + step)

            elif event.key == pygame.K_s:
                x, w = self.frame_positions[self.selected_frame]
                self.frame_positions[self.selected_frame] = (x, max(1, w - step))

            elif event.key == pygame.K_c:
                self.copy_positions()

        return True

    def copy_positions(self):
        """Print the current frame positions for copying."""
        print("\n" + "=" * 60)
        print("# Copy this to sprites.py FRAME_POSITIONS:")
        print("=" * 60)
        print(f"DUCK_START_Y = {DUCK_START_Y}")
        print(f"DUCK_ROW_HEIGHT = {DUCK_ROW_HEIGHT}")
        print(f"DUCK_SPRITE_HEIGHT = {DUCK_SPRITE_HEIGHT}")
        print()
        print("FRAME_POSITIONS = [")
        print("    # Level flight RIGHT (3 frames)")
        print(f"    {self.frame_positions[0]}, {self.frame_positions[1]}, {self.frame_positions[2]},")
        print("    # Diagonal UP_RIGHT (3 frames)")
        print(f"    {self.frame_positions[3]}, {self.frame_positions[4]}, {self.frame_positions[5]},")
        print("    # Shot/Hit still (1 frame)")
        print(f"    {self.frame_positions[6]},")
        print("    # Falling (4 frames)")
        print(f"    {self.frame_positions[7]}, {self.frame_positions[8]}, {self.frame_positions[9]}, {self.frame_positions[10]},")
        print("]")
        print("=" * 60 + "\n")

    def run(self):
        """Main loop."""
        clock = pygame.time.Clock()
        running = True

        while running:
            for event in pygame.event.get():
                running = self.handle_input(event)

            self.draw()
            clock.tick(30)

        pygame.quit()


if __name__ == "__main__":
    tuner = SpriteTuner()
    tuner.run()
