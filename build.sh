#!/bin/bash

# Build script for stash-away CLI tool

echo "Building stash-away executable..."

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "Error: PyInstaller not found. Install it with: pip install pyinstaller"
    exit 1
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/

# Build the executable
echo "Running PyInstaller..."
pyinstaller stash-away.spec

# Check if build was successful
if [ -f "dist/stash-away" ]; then
    echo "✅ Build successful! Executable created at: dist/stash-away"
    echo ""
    echo "To install system-wide, run:"
    echo "  sudo cp dist/stash-away /usr/local/bin/"
    echo ""
    echo "Or add to PATH:"
    echo "  export PATH=\$PATH:$(pwd)/dist"
else
    echo "❌ Build failed!"
    exit 1
fi