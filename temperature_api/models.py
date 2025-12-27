"""
Database models for Temperature Service.

Models:
- City: Represents a city with temperature data
- TemperatureReading: Individual temperature readings
- CityTemperatureCache: Cached temperature statistics
- FileUpload: Tracks uploaded files and their processing status
"""

from django.db import models
from django.db.models import Avg, Max, Min, Count
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class City(models.Model):
    """
    Represents a city that has temperature readings.
    
    Attributes:
        city_id: External identifier for the city
        name: Optional human-readable name
        created_at: When this city record was created
    """
    
    city_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="External identifier for the city"
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Human-readable city name"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Cities"
        ordering = ['city_id']

    def __str__(self):
        return f"City {self.city_id}"

    def get_statistics(self) -> dict:
        """
        Calculate temperature statistics for this city.
        
        Returns:
            Dictionary containing mean, max, min temperatures and reading count.
        """
        stats = self.temperature_readings.aggregate(
            mean_temp=Avg('temperature'),
            max_temp=Max('temperature'),
            min_temp=Min('temperature'),
            reading_count=Count('id')
        )
        return {
            'city_id': self.city_id,
            'mean_temperature': round(stats['mean_temp'], 2) if stats['mean_temp'] else None,
            'max_temperature': round(stats['max_temp'], 2) if stats['max_temp'] else None,
            'min_temperature': round(stats['min_temp'], 2) if stats['min_temp'] else None,
            'reading_count': stats['reading_count']
        }


class TemperatureReading(models.Model):
    """
    Individual temperature reading for a city.
    
    Attributes:
        city: Foreign key to the City model
        temperature: Temperature value in Celsius
        timestamp: When the reading was taken
        created_at: When this record was created in the database
    """
    
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name='temperature_readings',
        db_index=True
    )
    temperature = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[
            MinValueValidator(-100),  # Lowest recorded temp on Earth: -89.2°C
            MaxValueValidator(100)    # Highest recorded temp on Earth: 56.7°C
        ],
        help_text="Temperature in Celsius"
    )
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="When the temperature reading was taken"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['city', 'timestamp']),
            models.Index(fields=['city', 'temperature']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.city.city_id}: {self.temperature}°C at {self.timestamp}"


class CityTemperatureCache(models.Model):
    """
    Cached temperature statistics for a city.
    
    This table serves as an efficient cache layer to avoid
    recalculating statistics on every API request.
    
    Attributes:
        city: One-to-one relationship with City
        mean_temperature: Cached mean temperature
        max_temperature: Cached maximum temperature
        min_temperature: Cached minimum temperature
        reading_count: Total number of readings
        last_updated: When the cache was last refreshed
    """
    
    city = models.OneToOneField(
        City,
        on_delete=models.CASCADE,
        related_name='cache',
        primary_key=True
    )
    mean_temperature = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    max_temperature = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    min_temperature = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    reading_count = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    is_stale = models.BooleanField(
        default=False,
        help_text="Flag to indicate cache needs refresh"
    )

    class Meta:
        verbose_name = "City Temperature Cache"
        verbose_name_plural = "City Temperature Caches"

    def __str__(self):
        return f"Cache for {self.city.city_id}"

    def refresh(self):
        """Refresh cache from the actual temperature readings."""
        stats = self.city.get_statistics()
        self.mean_temperature = stats['mean_temperature']
        self.max_temperature = stats['max_temperature']
        self.min_temperature = stats['min_temperature']
        self.reading_count = stats['reading_count']
        self.is_stale = False
        self.save()

    def to_dict(self) -> dict:
        """Convert cache to dictionary for API response."""
        return {
            'city_id': self.city.city_id,
            'mean_temperature': float(self.mean_temperature) if self.mean_temperature else None,
            'max_temperature': float(self.max_temperature) if self.max_temperature else None,
            'min_temperature': float(self.min_temperature) if self.min_temperature else None,
            'reading_count': self.reading_count,
            'last_updated': self.last_updated.isoformat()
        }


class FileUpload(models.Model):
    """
    Tracks uploaded temperature data files and their processing status.
    
    Attributes:
        id: UUID primary key
        filename: Original filename
        file_size: Size of the file in bytes
        status: Current processing status
        total_rows: Total rows in the file
        processed_rows: Number of rows processed so far
        error_count: Number of errors encountered
        error_messages: JSON field storing error details
        celery_task_id: ID of the Celery task processing this file
        created_at: When the file was uploaded
        completed_at: When processing completed
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        PARTIALLY_COMPLETED = 'partial', 'Partially Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField(
        validators=[MinValueValidator(0)],
        help_text="File size in bytes"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    total_rows = models.PositiveIntegerField(default=0)
    processed_rows = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    error_messages = models.JSONField(default=list, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    retry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='file_uploads'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['celery_task_id']),
        ]

    def __str__(self):
        return f"{self.filename} ({self.status})"

    @property
    def progress_percentage(self) -> float:
        """Calculate processing progress as a percentage."""
        if self.total_rows == 0:
            return 0.0
        return round((self.processed_rows / self.total_rows) * 100, 2)

    def mark_completed(self):
        """Mark the file processing as completed."""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save()

    def mark_failed(self, error_message: str):
        """Mark the file processing as failed."""
        self.status = self.Status.FAILED
        self.error_messages.append({
            'timestamp': timezone.now().isoformat(),
            'message': error_message
        })
        self.completed_at = timezone.now()
        self.save()

    def add_error(self, error_message: str, row_number: int = None):
        """Add an error message to the error log."""
        self.error_count += 1
        self.error_messages.append({
            'timestamp': timezone.now().isoformat(),
            'row': row_number,
            'message': error_message
        })
        # Keep only last 100 errors to prevent memory issues
        if len(self.error_messages) > 100:
            self.error_messages = self.error_messages[-100:]
        self.save(update_fields=['error_count', 'error_messages', 'updated_at'])
