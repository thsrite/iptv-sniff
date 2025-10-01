#!/bin/bash
set -e

# Print environment information
echo "==================================="
echo "IPTV Sniffer Starting..."
echo "==================================="

# Check FFmpeg installation
if command -v ffmpeg &> /dev/null; then
    echo "FFmpeg version:"
    ffmpeg -version | head -n 1
else
    echo "WARNING: FFmpeg not found!"
fi

# Check hardware acceleration support
if command -v vainfo &> /dev/null; then
    echo ""
    echo "VA-API Information:"
    vainfo || echo "VA-API not available or no device found"
fi

echo ""
echo "==================================="

# Execute the main command
exec "$@"