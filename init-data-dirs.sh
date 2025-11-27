#!/bin/bash
# CYBERCOM Infrastructure - Data Directory Initialization
# Ensures .data directories exist with correct permissions before docker compose starts
#
# Cross-platform support: Linux, macOS, WSL
# Handles UID/GID mismatches across different systems

set -e

echo "[CYBERCOM] 🚀 Initializing data directories..."

# Detect OS using uname (more reliable than $OSTYPE)
OS="unknown"
UNAME_S=$(uname -s)
case "${UNAME_S}" in
    Linux*)
        if grep -qi microsoft /proc/version 2>/dev/null; then
            OS="wsl"
        else
            OS="linux"
        fi
        ;;
    Darwin*)
        OS="macos"
        ;;
    *)
        OS="linux"  # Default to Linux
        ;;
esac

echo "[CYBERCOM] Detected OS: $OS (uname: ${UNAME_S})"

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

# Platform-specific permission handling
if [ "$OS" = "macos" ]; then
    # macOS with Docker Desktop: VM handles UID mapping automatically
    echo "[CYBERCOM] macOS detected: Setting world-writable permissions..."
    echo "[CYBERCOM] (Docker Desktop VM handles UID mapping automatically)"
    chmod -R 777 .data/mysql 2>/dev/null || true
    chmod -R 777 .data/redis 2>/dev/null || true
    chmod -R 777 .data/CTFd/logs 2>/dev/null || true
    chmod -R 777 .data/CTFd/uploads 2>/dev/null || true
    echo "[CYBERCOM] ✅ Permissions set for macOS Docker Desktop"

else
    # Linux/WSL: Need to handle UID 999 manually
    OWNERSHIP_SET=false

    # Try proper ownership first (requires sudo)
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

    # Fallback: World-writable (works without sudo)
    if [ "$OWNERSHIP_SET" = false ]; then
        echo "[CYBERCOM] Setting world-writable permissions recursively..."
        echo "[CYBERCOM] (No sudo available or chown failed)"
        chmod -R 777 .data/mysql 2>/dev/null || true
        chmod -R 777 .data/redis 2>/dev/null || true
        chmod -R 777 .data/CTFd/logs 2>/dev/null || true
        chmod -R 777 .data/CTFd/uploads 2>/dev/null || true
        echo "[CYBERCOM] ✅ World-writable permissions set recursively"
    fi

    if [ "$OS" = "wsl" ]; then
        echo "[CYBERCOM] ℹ️  WSL detected: Ensure Docker Desktop integration is enabled"
    fi
fi

# Verify directories were created
if [ -d ".data/mysql" ] && [ -d ".data/redis" ]; then
    echo "[CYBERCOM] ✅ Data directories initialized successfully"
    echo "[CYBERCOM] Ready for: docker compose up -d"
else
    echo "[CYBERCOM] ❌ ERROR: Failed to create data directories"
    exit 1
fi
