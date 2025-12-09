#!/usr/bin/env python3
"""
AMS Web Controller - Mobile-controlled game launcher

Launches an AMS session controllable via web interface on your phone.
Open the displayed URL on your phone to:
- Select detection backend (mouse, laser, object)
- Run calibration
- Launch and control games
- Pause, resume, enter retrieval mode

Usage:
    # Start web-controlled AMS (default windowed)
    python ams_web.py

    # Fullscreen on secondary display (projector)
    python ams_web.py --fullscreen --display 1

    # Custom resolution
    python ams_web.py --resolution 1920x1080

    # Custom web port
    python ams_web.py --port 8888
"""

import pygame
import sys
import os
import argparse

# Add DuckHunt to path for imports (needed for some shared modules)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'games', 'DuckHunt'))

from ams.web_controller.ams_integration import AMSWebIntegration


def main():
    """Main entry point for web-controlled AMS."""

    parser = argparse.ArgumentParser(
        description='AMS Web Controller - Mobile-controlled game launcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start web-controlled AMS
  python ams_web.py

  # Fullscreen on projector (display 1)
  python ams_web.py --fullscreen --display 1

  # Custom port
  python ams_web.py --port 8888
        """
    )

    # Display settings
    parser.add_argument(
        '--fullscreen',
        action='store_true',
        help='Run in fullscreen mode'
    )
    parser.add_argument(
        '--display',
        type=int,
        default=0,
        help='Display index for fullscreen (0=primary, 1=secondary, etc.)'
    )
    parser.add_argument(
        '--resolution',
        type=str,
        default=None,
        help='Resolution as WIDTHxHEIGHT (e.g., 1920x1080). Auto-detected in fullscreen.'
    )

    # Web server settings
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind web server to (default: 0.0.0.0 for all interfaces)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='Port for web server (default: 8080)'
    )

    args = parser.parse_args()

    # Pre-enumerate network interfaces BEFORE creating fullscreen display
    # This triggers the macOS permission prompt while we can still see it
    print("Detecting network interfaces...")
    from ams.web_controller.ams_integration import get_local_ips, get_mdns_hostname
    local_ips = get_local_ips()
    mdns_hostname = get_mdns_hostname()

    print(f"  mDNS hostname: {mdns_hostname or 'not available'}")
    print(f"  Local IPs: {', '.join(local_ips)}")

    # Initialize pygame
    pygame.init()

    # Display settings
    if args.fullscreen:
        displays = pygame.display.get_desktop_sizes()
        print(f"\nAvailable displays: {len(displays)}")
        for i, size in enumerate(displays):
            print(f"  Display {i}: {size[0]}x{size[1]}")

        if args.display >= len(displays):
            print(f"\nWARNING: Display {args.display} not found, using display 0")
            display_index = 0
        else:
            display_index = args.display

        DISPLAY_WIDTH, DISPLAY_HEIGHT = displays[display_index]
        print(f"\nUsing display {display_index}: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")

        os.environ['SDL_VIDEO_WINDOW_POS'] = f"{sum(d[0] for d in displays[:display_index])},0"
        screen = pygame.display.set_mode(
            (DISPLAY_WIDTH, DISPLAY_HEIGHT),
            pygame.FULLSCREEN
        )
        print("Fullscreen mode enabled")
    else:
        if args.resolution:
            try:
                width, height = args.resolution.split('x')
                DISPLAY_WIDTH = int(width)
                DISPLAY_HEIGHT = int(height)
            except:
                print(f"Invalid resolution format: {args.resolution}, using default")
                DISPLAY_WIDTH = 1280
                DISPLAY_HEIGHT = 720
        else:
            DISPLAY_WIDTH = 1280
            DISPLAY_HEIGHT = 720

        screen = pygame.display.set_mode((DISPLAY_WIDTH, DISPLAY_HEIGHT))
        print(f"Windowed mode: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")

    pygame.display.set_caption("AMS Web Controller")

    print("=" * 60)
    print("AMS Web Controller")
    print("=" * 60)
    print(f"\nStarting web server on port {args.port}...")

    # Create integration
    integration = AMSWebIntegration(
        screen=screen,
        display_resolution=(DISPLAY_WIDTH, DISPLAY_HEIGHT),
        host=args.host,
        port=args.port,
    )

    # Start web server
    integration.start()

    print("\n" + "=" * 60)
    print(f"Web controller ready!")
    print(f"Open http://localhost:{args.port} on your phone")
    print("=" * 60)
    print("\nKeyboard controls:")
    print("  ESC - Stop current game / Exit")
    print("  F   - Toggle fullscreen")
    print("  D   - Toggle debug visualization (laser/object mode)")
    print()

    # Main loop
    clock = pygame.time.Clock()

    try:
        while integration.running:
            dt = clock.tick(60) / 1000.0  # 60 FPS

            # Handle pygame events
            events = pygame.event.get()
            if not integration.handle_pygame_events(events):
                break

            # Update integration
            if not integration.update(dt):
                break

            # Render
            integration.render()

    except KeyboardInterrupt:
        print("\n\nShutdown requested...")

    finally:
        # Cleanup
        print("\nCleaning up...")
        integration.stop()

        # Save session if exists
        if integration.ams_session:
            integration.ams_session.save_session()
            print("Session saved.")

        pygame.quit()
        print("Done!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
