#!/bin/bash
# CYBERCOM Infrastructure - Data Directory Initialization
# Ensures .data directories exist before docker compose starts

set -e

echo "[CYBERCOM] Initializing data directories..."

# Create required data directories
mkdir -p .data/mysql
mkdir -p .data/redis
mkdir -p .data/CTFd/logs
mkdir -p .data/CTFd/uploads

# Set permissions for database directories
chmod 755 .data/mysql
chmod 755 .data/redis
chmod 755 .data/CTFd/logs
chmod 755 .data/CTFd/uploads

echo "[CYBERCOM] ✅ Data directories initialized"
echo "[CYBERCOM] Ready for: docker compose up"
