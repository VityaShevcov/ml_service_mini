#!/bin/bash

# ML Chat Billing Service Deployment Script
# This script helps deploy the service in different environments

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="ml-chat-billing-service"
DOCKER_IMAGE="ml-chat-service"
BACKUP_DIR="./backups"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking requirements..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check Python (for local deployment)
    if ! command -v python3 &> /dev/null; then
        log_warning "Python 3 is not installed. Docker deployment only."
    fi
    
    log_success "Requirements check passed"
}

setup_environment() {
    log_info "Setting up environment..."
    
    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        log_info "Creating .env file from template..."
        cp .env.example .env
        log_warning "Please edit .env file with your configuration before proceeding"
        read -p "Press Enter to continue after editing .env file..."
    fi
    
    # Create necessary directories
    mkdir -p logs data backups ssl
    
    # Set permissions
    chmod 755 logs data backups
    
    log_success "Environment setup completed"
}

generate_ssl_certificates() {
    log_info "Generating self-signed SSL certificates..."
    
    if [ ! -f ssl/cert.pem ] || [ ! -f ssl/key.pem ]; then
        openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
        log_success "SSL certificates generated"
    else
        log_info "SSL certificates already exist"
    fi
}

backup_database() {
    log_info "Creating database backup..."
    
    timestamp=$(date +"%Y%m%d_%H%M%S")
    backup_file="${BACKUP_DIR}/db_backup_${timestamp}.sql"
    
    if docker-compose ps db | grep -q "Up"; then
        docker-compose exec -T db pg_dump -U postgres ml_chat_service > "$backup_file"
        log_success "Database backup created: $backup_file"
    else
        log_warning "Database container is not running, skipping backup"
    fi
}

deploy_local() {
    log_info "Deploying locally..."
    
    # Install Python dependencies
    if command -v python3 &> /dev/null; then
        log_info "Installing Python dependencies..."
        pip3 install -r requirements.txt
        
        # Run startup script
        log_info "Starting service..."
        python3 startup.py
    else
        log_error "Python 3 is required for local deployment"
        exit 1
    fi
}

deploy_docker() {
    log_info "Deploying with Docker..."
    
    # Build and start services
    log_info "Building Docker images..."
    docker-compose build
    
    log_info "Starting services..."
    docker-compose up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 10
    
    # Check service health
    if curl -f http://localhost:8000/health &> /dev/null; then
        log_success "API service is healthy"
    else
        log_error "API service health check failed"
    fi
    
    log_success "Docker deployment completed"
}

deploy_production() {
    log_info "Deploying for production..."
    
    # Backup existing database
    backup_database
    
    # Generate SSL certificates if needed
    generate_ssl_certificates
    
    # Deploy with production profile
    log_info "Starting production services..."
    docker-compose --profile production up -d --build
    
    # Wait for services
    sleep 15
    
    # Health check
    if curl -f -k https://localhost/health &> /dev/null; then
        log_success "Production deployment successful"
    else
        log_error "Production deployment health check failed"
    fi
}

deploy_monitoring() {
    log_info "Deploying with monitoring..."
    
    # Start services with monitoring profile
    docker-compose --profile monitoring up -d --build
    
    log_info "Monitoring services:"
    log_info "- Prometheus: http://localhost:9090"
    log_info "- Grafana: http://localhost:3000 (admin/admin)"
    
    log_success "Monitoring deployment completed"
}

stop_services() {
    log_info "Stopping services..."
    
    if [ -f docker-compose.yml ]; then
        docker-compose down
        log_success "Docker services stopped"
    fi
    
    # Kill any running Python processes
    pkill -f "python.*startup.py" || true
    pkill -f "uvicorn.*main:app" || true
    
    log_success "All services stopped"
}

cleanup() {
    log_info "Cleaning up..."
    
    # Stop services
    stop_services
    
    # Remove Docker containers and images
    docker-compose down -v --remove-orphans
    docker system prune -f
    
    log_success "Cleanup completed"
}

show_status() {
    log_info "Service Status:"
    
    # Check Docker services
    if command -v docker-compose &> /dev/null && [ -f docker-compose.yml ]; then
        docker-compose ps
    fi
    
    # Check local processes
    if pgrep -f "python.*startup.py" &> /dev/null; then
        log_info "Local Python service is running"
    fi
    
    # Check service endpoints
    log_info "Checking service endpoints..."
    
    if curl -f http://localhost:8000/health &> /dev/null; then
        log_success "API service: http://localhost:8000 ✓"
    else
        log_warning "API service: http://localhost:8000 ✗"
    fi
    
    if curl -f http://localhost:7861 &> /dev/null; then
        log_success "Gradio UI: http://localhost:7861 ✓"
    else
        log_warning "Gradio UI: http://localhost:7861 ✗"
    fi
}

show_logs() {
    log_info "Showing service logs..."
    
    if [ -f docker-compose.yml ]; then
        docker-compose logs -f --tail=100 ml-chat-service
    else
        log_warning "No Docker Compose file found"
        if [ -f logs/ml_chat_service.log ]; then
            tail -f logs/ml_chat_service.log
        else
            log_warning "No log file found"
        fi
    fi
}

show_help() {
    echo "ML Chat Billing Service Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  local       Deploy locally with Python"
    echo "  docker      Deploy with Docker Compose"
    echo "  production  Deploy for production with SSL and reverse proxy"
    echo "  monitoring  Deploy with monitoring stack (Prometheus + Grafana)"
    echo "  stop        Stop all services"
    echo "  status      Show service status"
    echo "  logs        Show service logs"
    echo "  backup      Create database backup"
    echo "  cleanup     Stop services and clean up Docker resources"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 docker          # Deploy with Docker"
    echo "  $0 production      # Deploy for production"
    echo "  $0 status          # Check service status"
    echo "  $0 logs            # View logs"
}

# Main script
main() {
    echo "🚀 ML Chat Billing Service Deployment"
    echo "======================================"
    
    case "${1:-help}" in
        "local")
            check_requirements
            setup_environment
            deploy_local
            ;;
        "docker")
            check_requirements
            setup_environment
            deploy_docker
            show_status
            ;;
        "production")
            check_requirements
            setup_environment
            deploy_production
            show_status
            ;;
        "monitoring")
            check_requirements
            setup_environment
            deploy_monitoring
            show_status
            ;;
        "stop")
            stop_services
            ;;
        "status")
            show_status
            ;;
        "logs")
            show_logs
            ;;
        "backup")
            backup_database
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Run main function with all arguments
main "$@"