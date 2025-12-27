"""
Pytest fixtures for Temperature API tests.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from temperature_api.models import City, TemperatureReading, CityTemperatureCache


@pytest.fixture
def api_client():
    """Return an API client instance."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def authenticated_client(api_client, user):
    """Return an authenticated API client."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def city(db):
    """Create a test city."""
    return City.objects.create(city_id='TEST_CITY_001', name='Test City')


@pytest.fixture
def cities(db):
    """Create multiple test cities."""
    return [
        City.objects.create(city_id=f'CITY_{i:03d}', name=f'City {i}')
        for i in range(1, 6)
    ]


@pytest.fixture
def temperature_readings(city):
    """Create temperature readings for a city."""
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    readings = []
    
    for i in range(100):
        readings.append(TemperatureReading(
            city=city,
            temperature=Decimal(str(20 + (i % 20) - 10)),
            timestamp=base_time + timedelta(hours=i)
        ))
    
    TemperatureReading.objects.bulk_create(readings)
    return TemperatureReading.objects.filter(city=city)


@pytest.fixture
def city_with_cache(city, temperature_readings):
    """Create a city with a populated cache."""
    cache = CityTemperatureCache.objects.create(city=city)
    cache.refresh()
    return city


@pytest.fixture
def sample_csv_content():
    """Return sample CSV content for testing."""
    lines = [
        'city_id,temp,timestamp',
        'CITY_001,25.5,2024-01-15T10:30:00Z',
        'CITY_001,26.0,2024-01-15T11:30:00Z',
        'CITY_002,18.5,2024-01-15T10:30:00Z',
        'CITY_002,19.0,2024-01-15T11:30:00Z',
    ]
    return '\n'.join(lines)


@pytest.fixture
def temp_csv_file(tmp_path, sample_csv_content):
    """Create a temporary CSV file for testing."""
    file_path = tmp_path / 'test_data.csv'
    file_path.write_text(sample_csv_content)
    return file_path
