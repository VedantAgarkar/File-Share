#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "=== Building LocalDrop Linux Binary & AppImage ==="

# Check pyinstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "PyInstaller not found in PATH, using python3 -m PyInstaller..."
    PYINSTALLER="python3 -m PyInstaller"
else
    PYINSTALLER="pyinstaller"
fi

# 1. Build standalone binary
echo "--> Compiling with PyInstaller..."
$PYINSTALLER --clean -y LocalDrop.spec

# 2. Package as AppDir
APPDIR="$DIR/build/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp "$DIR/dist/LocalDrop" "$APPDIR/usr/bin/LocalDrop"

# Desktop entry
cat << 'EOF' > "$APPDIR/localdrop.desktop"
[Desktop Entry]
Name=LocalDrop
Comment=Fast Cross-Device Local File Sharing
Exec=LocalDrop
Icon=localdrop
Type=Application
Categories=Network;FileTransfer;Utility;
Terminal=false
EOF

# AppRun script
cat << 'EOF' > "$APPDIR/AppRun"
#!/bin/sh
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/LocalDrop" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# Copy App icon
cp "$DIR/assets/icon.png" "$APPDIR/localdrop.png"
cp "$DIR/assets/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/localdrop.png"
cp "$APPDIR/localdrop.png" "$APPDIR/.DirIcon"

echo "--> AppDir assembled at $APPDIR"

# Download or run appimagetool if available, or create portable package
if ! command -v appimagetool &> /dev/null; then
    echo "Downloading appimagetool..."
    curl -L -s -o /tmp/appimagetool "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" || true
    chmod +x /tmp/appimagetool 2>/dev/null || true
    if [ -x /tmp/appimagetool ]; then
        TOOL="/tmp/appimagetool"
    fi
else
    TOOL="appimagetool"
fi

if [ -n "$TOOL" ]; then
    echo "--> Generating AppImage..."
    ARCH=x86_64 $TOOL "$APPDIR" "$DIR/dist/LocalDrop-x86_64.AppImage" || true
fi

if [ -f "$DIR/dist/LocalDrop-x86_64.AppImage" ]; then
    echo "✓ AppImage successfully built at: dist/LocalDrop-x86_64.AppImage"
else
    echo "AppImage tool required FUSE or container extraction. Created portable Linux executable bundle at dist/LocalDrop"
fi
