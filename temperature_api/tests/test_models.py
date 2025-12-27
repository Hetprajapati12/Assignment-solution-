"""
Tests for Temperature API models.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError

from temperature_api.models import City, TemperatureReading, CityTemperatureCache, FileUpload


@pytest.mark.django_db
class TestCityModel:
    """Tests for the City model."""
    
    def test_create_city(self):
        """Test creating a city."""
        city = City.objects.create(city_id='NYC', name='New York City')
        
        assert city.city_id == 'NYC'
        assert city.name == 'New York City'
        assert city.created_at is not None
    
    def test_city_str_representation(self):
        """Test city string representation."""
        city = City.objects.create(city_id='LAX')
        assert str(city) == 'City LAX'
    
    def test_city_unique_constraint(self):
        """Test that city_id must be unique."""
        City.objects.create(city_id='UNIQUE_001')
        
        with pytest.raises(Exception):
            City.objects.create(city_id='UNIQUE_001')
    
    def test_get_statistics_empty(self):
        """Test statistics for city with no readings."""
        city = City.objects.create(city_id='EMPTY')
        stats = city.get_statistics()
        
        assert stats['city_id'] == 'EMPTY'
        assert stats['mean_temperature'] is None
        assert stats['max_temperature'] is None
        assert stats['min_temperature'] is None
        assert stats['reading_count'] == 0
    
    def test_get_statistics_with_readings(self, city, temperature_readings):
        """Test statistics calculation with readings."""
        stats = city.get_statistics()
        
        assert stats['city_id'] == city.city_id
        assert stats['mean_temperature'] is not None
        assert stats['max_temperature'] is not None
        assert stats['min_temperature'] is not None
        assert stats['reading_count'] == 100


@pytest.mark.django_db
class TestTemperatureReadingModel:
    """Tests for the TemperatureReading model."""
    
    def test_create_reading(self, city):
        """Test creating a temperature reading."""
        reading = TemperatureReading.objects.create(
            city=city,
            temperature=Decimal('25.50'),
            timestamp=timezone.now()
        )
        
        assert reading.temperature == Decimal('25.50')
        assert reading.city == city
    
    def test_reading_str_representation(self, city):
        """Test reading string representation."""
        reading = TemperatureReading.objects.create(
            city=city,
            temperature=Decimal('25.50'),
            timestamp=timezone.now()
        )
        
        assert city.city_id in str(reading)
        assert '25.50' in str(reading)
    
    def test_temperature_validation_too_low(self, city):
        """Test that extremely low temperatures are rejected."""
        reading = TemperatureReading(
            city=city,
            temperature=Decimal('-150'),
            timestamp=timezone.now()
        )
        
        with pytest.raises(ValidationError):
            reading.full_clean()
    
    def test_temperature_validation_too_high(self, city):
        """Test that extremely high temperatures are rejected."""
        reading = TemperatureReading(
            city=city,
            temperature=Decimal('150'),
            timestamp=timezone.now()
        )
        
        with pytest.raises(ValidationError):
            reading.full_clean()


@pytest.mark.django_db
class TestCityTemperatureCacheModel:
    """Tests for the CityTemperatureCache model."""
    
    def test_create_cache(self, city):
        """Test creating a cache entry."""
        cache = CityTemperatureCache.objects.create(city=city)
        
        assert cache.city == city
        assert cache.reading_count == 0
        assert cache.is_stale is False
    
    def test_cache_refresh(self, city, temperature_readings):
        """Test refreshing cache with readings."""
        cache = CityTemperatureCache.objects.create(city=city)
        cache.refresh()
        
        assert cache.mean_temperature is not None
        assert cache.max_temperature is not None
        assert cache.min_temperature is not None
        assert cache.reading_count == 100
        assert cache.is_stale is False
    
    def test_cache_to_dict(self, city, temperature_readings):
        """Test cache to_dict method."""
        cache = CityTemperatureCache.objects.create(city=city)
        cache.refresh()
        
        data = cache.to_dict()
        
        assert 'city_id' in data
        assert 'mean_temperature' in data
        assert 'max_temperature' in data
        assert 'min_temperature' in data
        assert 'reading_count' in data
        assert 'last_updated' in data


@pytest.mark.django_db
class TestFileUploadModel:
    """Tests for the FileUpload model."""
    
    def test_create_file_upload(self, user):
        """Test creating a file upload record."""
        upload = FileUpload.objects.create(
            filename='test.csv',
            file_path='/tmp/test.csv',
            file_size=1024,
            uploaded_by=user
        )
        
        assert upload.filename == 'test.csv'
        assert upload.status == FileUpload.Status.PENDING
        assert upload.progress_percentage == 0.0
    
    def test_progress_percentage(self):
        """Test progress percentage calculation."""
        upload = FileUpload.objects.create(
            filename='test.csv',
            file_path='/tmp/test.csv',
            file_size=1024,
            total_rows=100,
            processed_rows=50
        )
        
        assert upload.progress_percentage == 50.0
    
    def test_mark_completed(self):
        """Test marking upload as completed."""
        upload = FileUpload.objects.create(
            filename='test.csv',
            file_path='/tmp/test.csv',
            file_size=1024
        )
        
        upload.mark_completed()
        
        assert upload.status == FileUpload.Status.COMPLETED
        assert upload.completed_at is not None
    
    def test_mark_failed(self):
        """Test marking upload as failed."""
        upload = FileUpload.objects.create(
            filename='test.csv',
            file_path='/tmp/test.csv',
            file_size=1024
        )
        
        upload.mark_failed('Test error message')
        
        assert upload.status == FileUpload.Status.FAILED
        assert len(upload.error_messages) == 1
        assert upload.error_messages[0]['message'] == 'Test error message'
    
    def test_add_error(self):
        """Test adding errors to upload."""
        upload = FileUpload.objects.create(
            filename='test.csv',
            file_path='/tmp/test.csv',
            file_size=1024
        )
        
        upload.add_error('Error 1', row_number=10)
        upload.add_error('Error 2', row_number=20)
        
        assert upload.error_count == 2
        assert len(upload.error_messages) == 2
