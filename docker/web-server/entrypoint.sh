#!/bin/bash
set -e

echo "=== YAMS Web Server Starting ==="

# Build directory (writable) - use subdirectory of volume mount
VOLUME_DIR="/build/web"
BUILD_DIR="$VOLUME_DIR/output"
BUILD_MARKER="$VOLUME_DIR/.build_complete"

# Check if build is needed
if [ ! -f "$BUILD_MARKER" ] || [ "$FORCE_REBUILD" = "1" ]; then
    echo "Building pygbag bundle..."

    # Clean old build if exists
    rm -rf "$BUILD_DIR" 2>/dev/null || true

    # Run the build script with custom output directory
    cd /app
    python games/browser/build.py --output "$BUILD_DIR"

    # Mark build complete
    touch "$BUILD_MARKER"
    echo "Build complete!"
else
    echo "Using existing build (set FORCE_REBUILD=1 to rebuild)"
fi

# Export BUILD_DIR for server.py
export BUILD_DIR

# Start the web server
echo "Starting web server..."
exec python /server.py
