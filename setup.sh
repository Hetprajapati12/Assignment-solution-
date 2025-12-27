#!/bin/bash
# setup.sh - Automated setup script for Temperature Service

set -e

echo "=========================================="
echo "  Temperature Service - Local Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Check prerequisites
echo "Step 1: Checking prerequisites..."

if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    print_status "Python 3 found: $PYTHON_VERSION"
else
    print_error "Python 3 is not installed. Please install Python 3.10+"
    exit 1
fi

if command_exists psql; then
    print_status "PostgreSQL client found"
else
    print_warning "PostgreSQL client not found. Make sure PostgreSQL is installed."
fi

if command_exists redis-cli; then
    if redis-cli ping > /dev/null 2>&1; then
        print_status "Redis is running"
    else
        print_warning "Redis is installed but not running. Please start Redis."
    fi
else
    print_warning "Redis CLI not found. Make sure Redis is installed and running."
fi

echo ""

# Step 2: Create virtual environment
echo "Step 2: Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_status "Virtual environment created"
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate
print_status "Virtual environment activated"

echo ""

# Step 3: Install dependencies
echo "Step 3: Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
print_status "Dependencies installed"

echo ""

# Step 4: Create .env file if not exists
echo "Step 4: Configuring environment..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    print_status ".env file created from template"
    print_warning "Please edit .env file with your database credentials"
else
    print_status ".env file already exists"
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

echo ""

# Step 5: Create directories
echo "Step 5: Creating required directories..."
mkdir -p logs media/uploads
print_status "Directories created"

echo ""

# Step 6: Database setup
echo "Step 6: Setting up database..."

# Check if database exists
if PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw $POSTGRES_DB; then
    print_status "Database '$POSTGRES_DB' already exists"
else
    print_warning "Database '$POSTGRES_DB' does not exist."
    echo "Please create it manually with:"
    echo "  sudo -u postgres psql -c \"CREATE DATABASE $POSTGRES_DB;\""
    echo ""
fi

echo ""

# Step 7: Run migrations
echo "Step 7: Running database migrations..."
python manage.py migrate --noinput
print_status "Migrations completed"

echo ""

# Step 8: Create cache table
echo "Step 8: Creating cache table..."
python manage.py createcachetable 2>/dev/null || true
print_status "Cache table ready"

echo ""

# Step 9: Generate test data
echo "Step 9: Generating sample test data..."
python scripts/generate_test_data.py --rows 100 --output test_data_sample.csv
print_status "Sample test data created: test_data_sample.csv"

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "To run the application, open 3 terminal windows:"
echo ""
echo "Terminal 1 (Django Server):"
echo "  source venv/bin/activate"
echo "  export \$(cat .env | xargs)"
echo "  python manage.py runserver"
echo ""
echo "Terminal 2 (Celery Worker):"
echo "  source venv/bin/activate"
echo "  export \$(cat .env | xargs)"
echo "  celery -A config worker -l INFO"
echo ""
echo "Terminal 3 (Celery Beat - Optional):"
echo "  source venv/bin/activate"
echo "  export \$(cat .env | xargs)"
echo "  celery -A config beat -l INFO"
echo ""
echo "API will be available at: http://localhost:8000"
echo "Health check: http://localhost:8000/api/health/"
echo ""
