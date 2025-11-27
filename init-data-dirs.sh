#!/bin/bash
# CYBERCOM Infrastructure - Data Directory Initialization
# Ensures .data directories exist with correct permissions before docker compose starts
#
# Cross-platform support: Linux, macOS, WSL
# Handles UID/GID mismatches across different systems

set -e

echo "[CYBERCOM] 🚀 Initializing data directories..."

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
    OS="wsl"
else
    OS="linux"  # Default to Linux
fi

echo "[CYBERCOM] Detected OS: $OS"

# Create required data directories
echo "[CYBERCOM] Creating directory structure..."
mkdir -p .data/mysql
mkdir -p .data/redis
mkdir -p .data/CTFd/logs
mkdir -p .data/CTFd/uploads

# CRITICAL: Docker containers run with specific UIDs
# - MariaDB: UID 999
# - Redis: UID 999
# - CTFd: root (but writes to CTFd dirs)

# Strategy: Try proper ownership first, fall back to world-writable
OWNERSHIP_SET=false

# Check if we can use sudo for proper ownership
if command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
    echo "[CYBERCOM] Setting proper ownership (UID 999 for database containers)..."
    if sudo chown -R 999:999 .data/mysql .data/redis 2>/dev/null; then
        chmod -R 755 .data/mysql
        chmod -R 755 .data/redis
        chmod -R 755 .data/CTFd/logs
        chmod -R 755 .data/CTFd/uploads
        OWNERSHIP_SET=true
        echo "[CYBERCOM] ✅ Proper ownership set recursively (UID 999)"
    fi
fi

# Fallback: World-writable (works on all systems without sudo)
if [ "$OWNERSHIP_SET" = false ]; then
    echo "[CYBERCOM] Setting world-writable permissions recursively (no sudo available)..."
    chmod -R 777 .data/mysql
    chmod -R 777 .data/redis
    chmod -R 777 .data/CTFd/logs
    chmod -R 777 .data/CTFd/uploads
    echo "[CYBERCOM] ✅ World-writable permissions set recursively (fixes existing files)"
fi

# Platform-specific notes
if [ "$OS" = "macos" ]; then
    echo "[CYBERCOM] ℹ️  macOS detected: Docker Desktop handles UID mapping automatically"
elif [ "$OS" = "wsl" ]; then
    echo "[CYBERCOM] ℹ️  WSL detected: Ensure Docker Desktop integration is enabled"
fi

# Verify directories were created
if [ -d ".data/mysql" ] && [ -d ".data/redis" ]; then
    echo "[CYBERCOM] ✅ Data directories initialized successfully"
    echo "[CYBERCOM] Ready for: docker compose up -d"
else
    echo "[CYBERCOM] ❌ ERROR: Failed to create data directories"
    exit 1
fi
