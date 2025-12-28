# Temperature Service API

A production-grade Django REST API service for processing and storing large temperature reading files.

## Prerequisites

Before running this application, ensure you have the following installed:

1. **Python 3.10+**
2. **PostgreSQL 14+**
3. **Redis 7+**

### Installing Prerequisites

#### On Windows:
1. Download and install [PostgreSQL](https://www.postgresql.org/download/windows/)
2. Download and install [Redis for Windows](https://github.com/microsoftarchive/redis/releases) or use WSL2
3. Download and install [Python](https://www.python.org/downloads/windows/)

---

## Step-by-Step Setup

### Step 1: Create PostgreSQL Database

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# In PostgreSQL prompt, run:
CREATE DATABASE temperature_db;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE temperature_db TO postgres;
ALTER USER postgres WITH SUPERUSER;
\q
```

Or if you already have a postgres user with a password:
```bash
psql -U postgres -c "CREATE DATABASE temperature_db;"
```

### Step 2: Verify Redis is Running

```bash
redis-cli ping
# Should return: PONG
```

### Step 3: Set Up Python Virtual Environment

```bash
# Navigate to project directory
cd temperature_service_local

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Step 4: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your database credentials if different
# nano .env  OR  vim .env  OR open in your preferred editor
```

**Important**: Update `.env` with your PostgreSQL credentials:
```
POSTGRES_DB=temperature_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

### Step 6: Set Environment Variables

```bash

# On Windows PowerShell:
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
    }
}

# On Windows CMD:
for /f "tokens=1,2 delims==" %a in (.env) do set %a=%b
```

### Step 7: Run Database Migrations

```bash
python manage.py migrate
```

### Step 8: Create Cache Table

```bash
python manage.py createcachetable
```

### Step 9: Create Admin User (Optional)

```bash
python manage.py createsuperuser
```

---

## Running the Application

You need **3 terminal windows** to run all components:

### Terminal 1: Django Development Server

```bash
cd temperature_service_local
source venv/bin/activate  # On Windows: venv\Scripts\activate
export $(cat .env | xargs)  # Set environment variables

python manage.py runserver
```

The API will be available at: `http://localhost:8000`

### Terminal 2: Celery Worker

```bash
cd temperature_service_local
source venv/bin/activate
export $(cat .env | xargs)

celery -A config worker -l INFO -Q file_processing,chunk_processing,cache_updates,celery --concurrency=4
```

### Terminal 3: Celery Beat (Scheduler) - Optional

```bash
cd temperature_service_local
source venv/bin/activate
export $(cat .env | xargs)

celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Quick Test

### 1. Check Health Endpoint

```bash
curl http://localhost:8000/api/health/
```

Expected response:
```json
{"status": "healthy", "service": "temperature-service", "version": "1.0.0"}
```

### 2. Register a User

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!"
  }'
```

### 3. Get JWT Token

```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "SecurePass123!"
  }'
```

Save the `access` token from the response.

### 4. Generate Test Data

```bash
python scripts/generate_test_data.py --rows 1000 --output test_data.csv
```

### 5. Upload Test Data

```bash
curl -X POST http://localhost:8000/api/upload/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE" \
  -F "file=@test_data.csv"
```

### 6. Check Upload Status

```bash
curl http://localhost:8000/api/upload/UPLOAD_ID_HERE/status/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

### 7. Get Temperature Statistics

```bash
curl http://localhost:8000/api/cities/CITY_0001/statistics/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

---

## API Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/health/` | Health check | No |
| POST | `/api/auth/register/` | Register user | No |
| POST | `/api/auth/token/` | Get JWT token | No |
| POST | `/api/auth/token/refresh/` | Refresh token | No |
| GET | `/api/cities/` | List all cities | Yes |
| GET | `/api/cities/{city_id}/` | Get city details | Yes |
| GET | `/api/cities/{city_id}/statistics/` | Get temperature stats | Yes |
| GET | `/api/cities/{city_id}/readings/` | Get readings | Yes |
| POST | `/api/upload/` | Upload CSV file | Yes |
| GET | `/api/upload/{id}/status/` | Check upload status | Yes |
| GET | `/api/uploads/` | List all uploads | Yes |

---

## CSV File Format

```csv
city_id,temp,timestamp
NYC,25.5,2024-01-15T10:30:00Z
LAX,18.2,2024-01-15T10:30:00Z
CHI,-5.0,2024-01-15T10:30:00Z
```

---

## Running Tests

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=temperature_api --cov-report=html

# Run specific test file
pytest temperature_api/tests/test_api.py -v
```

