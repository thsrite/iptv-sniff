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

echo ""
echo "==================================="

# Execute the main command
exec "$@"