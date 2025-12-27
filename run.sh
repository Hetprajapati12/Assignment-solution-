#!/bin/bash
# run.sh - Start all Temperature Service components
# Usage: ./run.sh [web|worker|beat|all]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found. Run setup.sh first."
    exit 1
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo ".env file not found. Copy from .env.example"
    exit 1
fi

# Function to start Django server
start_web() {
    echo -e "${GREEN}Starting Django development server...${NC}"
    python manage.py runserver 0.0.0.0:8000
}

# Function to start Celery worker
start_worker() {
    echo -e "${GREEN}Starting Celery worker...${NC}"
    celery -A config worker -l INFO -Q file_processing,chunk_processing,cache_updates,celery --concurrency=4
}

# Function to start Celery beat
start_beat() {
    echo -e "${GREEN}Starting Celery beat scheduler...${NC}"
    celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
}

# Function to start Flower monitoring
start_flower() {
    echo -e "${GREEN}Starting Flower monitoring (http://localhost:5555)...${NC}"
    celery -A config flower --port=5555
}

# Main logic
case "${1:-web}" in
    web)
        start_web
        ;;
    worker)
        start_worker
        ;;
    beat)
        start_beat
        ;;
    flower)
        start_flower
        ;;
    all)
        echo -e "${YELLOW}Starting all services in background...${NC}"
        echo "Use 'pkill -f celery' and 'pkill -f runserver' to stop"
        echo ""
        
        # Start worker in background
        celery -A config worker -l INFO -Q file_processing,chunk_processing,cache_updates,celery --concurrency=4 &
        WORKER_PID=$!
        echo "Celery worker started (PID: $WORKER_PID)"
        
        # Start beat in background
        celery -A config beat -l INFO &
        BEAT_PID=$!
        echo "Celery beat started (PID: $BEAT_PID)"
        
        sleep 2
        
        # Start Django in foreground
        echo ""
        echo -e "${GREEN}Starting Django server (Ctrl+C to stop all)...${NC}"
        python manage.py runserver 0.0.0.0:8000
        
        # Cleanup on exit
        kill $WORKER_PID 2>/dev/null
        kill $BEAT_PID 2>/dev/null
        ;;
    *)
        echo "Usage: ./run.sh [web|worker|beat|flower|all]"
        echo ""
        echo "Commands:"
        echo "  web     - Start Django development server (default)"
        echo "  worker  - Start Celery worker"
        echo "  beat    - Start Celery beat scheduler"
        echo "  flower  - Start Flower monitoring dashboard"
        echo "  all     - Start all services (web, worker, beat)"
        exit 1
        ;;
esac
