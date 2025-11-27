#!/bin/bash
# CYBERCOM Infrastructure - One-Command Deployment Script
# Automates the entire deployment process for maximum reliability
#
# Usage: ./deploy.sh
# Sudo password: kali (for Linux/WSL)

set -e

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   CYBERCOM CTF 2026 - Infrastructure Deployment          ║"
echo "║   Automated Setup for Linux, macOS, and WSL              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ ERROR: $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Step 1: Check for Docker
echo "[1/5] Checking for Docker..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    echo ""
    print_info "Install Docker:"
    print_info "  macOS:  https://docs.docker.com/desktop/install/mac-install/"
    print_info "  Linux:  https://docs.docker.com/engine/install/"
    print_info "  WSL:    https://docs.docker.com/desktop/wsl/"
    exit 1
fi
print_success "Docker found: $(docker --version)"

# Step 2: Check for Docker Compose
echo ""
echo "[2/5] Checking for Docker Compose..."
if ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not available"
    print_info "Docker Compose is included with Docker Desktop"
    print_info "For standalone Docker Engine, install: sudo apt-get install docker-compose-plugin"
    exit 1
fi
print_success "Docker Compose found: $(docker compose version)"

# Step 3: Initialize data directories
echo ""
echo "[3/5] Initializing data directories..."
if [ ! -f "./init-data-dirs.sh" ]; then
    print_error "init-data-dirs.sh not found in current directory"
    print_info "Make sure you're running this from the repository root"
    exit 1
fi

chmod +x ./init-data-dirs.sh
./init-data-dirs.sh

if [ ! -d ".data/mysql" ] || [ ! -d ".data/redis" ]; then
    print_error "Data directories were not created properly"
    exit 1
fi
print_success "Data directories initialized"

# Step 4: Validate Docker is running
echo ""
echo "[4/5] Validating Docker daemon..."
if ! docker info &> /dev/null; then
    print_error "Docker daemon is not running"
    print_info "Start Docker Desktop or run: sudo systemctl start docker"
    exit 1
fi
print_success "Docker daemon is running"

# Step 5: Deploy with Docker Compose
echo ""
echo "[5/5] Deploying CYBERCOM infrastructure..."
print_info "This may take 2-4 minutes on first run (downloading images)..."
print_info "Database health check allows up to 4 minutes for initialization"

if docker compose up -d; then
    echo ""
    print_success "Deployment initiated successfully!"
    echo ""
    print_info "Waiting for services to become healthy..."
    print_info "(This is normal - database initialization takes time)"

    # Wait a bit for containers to start
    sleep 5

    # Show status
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Service Status:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    docker compose ps

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_success "Deployment Complete!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    print_info "Access the platform:"
    echo "  🌐 Web Interface:  http://localhost"
    echo "  🔧 Direct Access:  http://localhost:8000"
    echo ""
    print_info "Useful commands:"
    echo "  📊 View logs:      docker compose logs -f"
    echo "  🔍 Check status:   docker compose ps"
    echo "  🛑 Stop services:  docker compose down"
    echo "  🔄 Restart:        docker compose restart"
    echo ""
    print_warning "If database is still initializing, wait 1-2 minutes and check:"
    echo "  docker compose logs db"
    echo ""

else
    echo ""
    print_error "Deployment failed!"
    echo ""
    print_info "Troubleshooting steps:"
    echo "  1. Check logs:           docker compose logs"
    echo "  2. Check database:       docker compose logs db"
    echo "  3. Check if ports busy:  lsof -i :80 -i :8000 -i :3306"
    echo "  4. Clean restart:        docker compose down && ./deploy.sh"
    echo ""
    print_info "Common issues:"
    echo "  • Port already in use:   Stop conflicting services"
    echo "  • Permission denied:     Ensure Docker has permissions"
    echo "  • DB unhealthy:          Wait 2-4 minutes for initialization"
    echo ""
    exit 1
fi
