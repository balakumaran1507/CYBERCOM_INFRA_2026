#!/bin/bash
# CYBERCOM Infrastructure - Data Directory Initialization
# Ensures .data directories exist with correct permissions before docker compose starts

set -e

echo "[CYBERCOM] Initializing data directories..."

# Create required data directories
mkdir -p .data/mysql
mkdir -p .data/redis
mkdir -p .data/CTFd/logs
mkdir -p .data/CTFd/uploads

# CRITICAL: Docker containers run with specific UIDs
# - MariaDB: UID 999
# - Redis: UID 999
# - CTFd: root (but writes to CTFd dirs)

# Option 1: World-writable (works everywhere, less secure)
echo "[CYBERCOM] Setting permissions (world-writable for Docker compatibility)..."
chmod 777 .data/mysql
chmod 777 .data/redis
chmod 777 .data/CTFd/logs
chmod 777 .data/CTFd/uploads

# Option 2: Proper ownership (requires sudo, more secure)
# Uncomment if you have sudo access:
# echo "[CYBERCOM] Setting ownership to UID 999 (database/cache containers)..."
# sudo chown -R 999:999 .data/mysql
# sudo chown -R 999:999 .data/redis
# chmod 755 .data/mysql
# chmod 755 .data/redis

echo "[CYBERCOM] ✅ Data directories initialized"
echo "[CYBERCOM] Ready for: docker compose up"
