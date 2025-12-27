"""
Celery tasks for Temperature Service.

Tasks:
- process_temperature_file: Main task to process uploaded files
- process_file_chunk: Process a chunk of temperature readings
- update_city_cache: Update cache for a specific city
- refresh_all_city_caches: Refresh cache for all cities
"""

import csv
import logging
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any

from celery import shared_task, chain, group, chord
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import City, TemperatureReading, CityTemperatureCache, FileUpload
from django.db.models import F

logger = logging.getLogger(__name__)


class FileProcessingError(Exception):
    """Custom exception for file processing errors."""
    pass


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse timestamp string to datetime object.
    
    Supports multiple formats:
    - ISO 8601: 2024-01-15T10:30:00Z
    - ISO 8601 with timezone: 2024-01-15T10:30:00+00:00
    - Common formats: 2024-01-15 10:30:00
    - Unix timestamp: 1705315800
    """
    timestamp_str = str(timestamp_str).strip()
    
    # Try Unix timestamp first
    try:
        ts = float(timestamp_str)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        pass
    
    # Try various datetime formats
    formats = [
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%d/%m/%Y %H:%M:%S',
        '%m/%d/%Y %H:%M:%S',
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt, timezone.utc)
            return dt
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse timestamp: {timestamp_str}")


def parse_temperature(temp_str: str) -> Decimal:
    """Parse temperature string to Decimal."""
    try:
        temp = Decimal(str(temp_str).strip())
        if temp < -100 or temp > 100:
            raise ValueError(f"Temperature {temp} out of valid range (-100 to 100)")
        return temp
    except InvalidOperation:
        raise ValueError(f"Invalid temperature value: {temp_str}")


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_temperature_file(self, file_upload_id: str) -> Dict[str, Any]:
    """
    Main task to process an uploaded temperature file.
    
    This task:
    1. Reads the file in chunks
    2. Dispatches chunk processing tasks
    3. Updates the file upload status
    4. Triggers cache updates for affected cities
    
    Args:
        file_upload_id: UUID of the FileUpload record
        
    Returns:
        Dictionary with processing results
    """
    logger.info(f"Starting file processing for upload {file_upload_id}")
    
    try:
        file_upload = FileUpload.objects.get(id=file_upload_id)
    except FileUpload.DoesNotExist:
        logger.error(f"FileUpload {file_upload_id} not found")
        raise FileProcessingError(f"FileUpload {file_upload_id} not found")
    
    # Update status to processing
    file_upload.status = FileUpload.Status.PROCESSING
    file_upload.celery_task_id = self.request.id
    file_upload.save()
    
    try:
        file_path = file_upload.file_path
        
        if not os.path.exists(file_path):
            raise FileProcessingError(f"File not found: {file_path}")
        
        # Count total rows first
        with open(file_path, 'r', encoding='utf-8') as f:
            # Skip header if present
            first_line = f.readline()
            has_header = 'city_id' in first_line.lower() or 'temp' in first_line.lower()
            
            total_rows = sum(1 for _ in f)
            if not has_header:
                total_rows += 1  # Include first line if not header
        
        file_upload.total_rows = total_rows
        file_upload.save(update_fields=['total_rows', 'updated_at'])
        
        chunk_size = settings.TEMPERATURE_PROCESSING['CHUNK_SIZE']
        chunks_processed = 0
        affected_cities = set()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            # Skip header if present
            first_row = next(reader, None)
            if first_row and not ('city_id' in str(first_row[0]).lower()):
                # First row is data, not header
                chunk = [first_row]
            else:
                chunk = []
            
            for row in reader:
                chunk.append(row)
                
                if len(chunk) >= chunk_size:
                    # Process chunk synchronously for reliability
                    result = process_file_chunk(
                        file_upload_id=str(file_upload_id),
                        chunk_data=chunk,
                        chunk_number=chunks_processed
                    )
                    affected_cities.update(result.get('cities', []))
                    chunks_processed += 1
                    chunk = []
            
            # Process remaining rows
            if chunk:
                result = process_file_chunk(
                    file_upload_id=str(file_upload_id),
                    chunk_data=chunk,
                    chunk_number=chunks_processed
                )
                affected_cities.update(result.get('cities', []))
        
        # Refresh file upload from database
        file_upload.refresh_from_db()
        
        # Update caches for affected cities
        for city_id in affected_cities:
            update_city_cache.delay(city_id)
        
        # Mark as completed or partially completed
        if file_upload.error_count == 0:
            file_upload.mark_completed()
        else:
            file_upload.status = FileUpload.Status.PARTIALLY_COMPLETED
            file_upload.completed_at = timezone.now()
            file_upload.save()
        
        logger.info(
            f"File processing completed for {file_upload_id}: "
            f"{file_upload.processed_rows} rows processed, "
            f"{file_upload.error_count} errors"
        )
        
        return {
            'status': 'completed',
            'file_upload_id': str(file_upload_id),
            'processed_rows': file_upload.processed_rows,
            'error_count': file_upload.error_count,
            'affected_cities': list(affected_cities)
        }
        
    except Exception as e:
        logger.exception(f"Error processing file {file_upload_id}: {str(e)}")
        
        file_upload.refresh_from_db()
        file_upload.retry_count += 1
        file_upload.save(update_fields=['retry_count', 'updated_at'])
        
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            file_upload.mark_failed(str(e))
            raise


@shared_task(
    bind=True,
    autoretry_for=(IntegrityError,),
    retry_backoff=True,
    max_retries=5,
)
def process_file_chunk(
    self,
    file_upload_id: str,
    chunk_data: List[List[str]],
    chunk_number: int
) -> Dict[str, Any]:
    """
    Process a chunk of temperature readings.
    
    Args:
        file_upload_id: UUID of the FileUpload record
        chunk_data: List of rows to process
        chunk_number: Chunk sequence number for logging
        
    Returns:
        Dictionary with processing results
    """
    logger.debug(f"Processing chunk {chunk_number} for upload {file_upload_id}")
    
    try:
        file_upload = FileUpload.objects.get(id=file_upload_id)
    except FileUpload.DoesNotExist:
        logger.error(f"FileUpload {file_upload_id} not found")
        return {'error': 'FileUpload not found'}
    
    batch_size = settings.TEMPERATURE_PROCESSING['BATCH_SIZE']
    readings_to_create = []
    cities_cache = {}
    affected_cities = set()
    processed_count = 0
    error_count = 0
    
    for row_idx, row in enumerate(chunk_data):
        try:
            if len(row) < 3:
                raise ValueError(f"Row has {len(row)} columns, expected 3")
            
            city_id = str(row[0]).strip()
            temperature = parse_temperature(row[1])
            timestamp = parse_timestamp(row[2])
            
            # Get or create city (using cache to reduce DB queries)
            if city_id not in cities_cache:
                city, _ = City.objects.get_or_create(city_id=city_id)
                cities_cache[city_id] = city
            else:
                city = cities_cache[city_id]
            
            affected_cities.add(city_id)
            
            readings_to_create.append(TemperatureReading(
                city=city,
                temperature=temperature,
                timestamp=timestamp
            ))
            processed_count += 1
            
            # Batch insert when batch size reached
            if len(readings_to_create) >= batch_size:
                with transaction.atomic():
                    TemperatureReading.objects.bulk_create(
                        readings_to_create,
                        ignore_conflicts=False,
                        batch_size=batch_size
                    )
                readings_to_create = []
                
        except (ValueError, ValidationError) as e:
            error_count += 1
            row_number = (chunk_number * settings.TEMPERATURE_PROCESSING['CHUNK_SIZE']) + row_idx + 1
            file_upload.add_error(str(e), row_number)
            logger.warning(f"Error processing row {row_number}: {str(e)}")
    
    # Insert remaining readings
    if readings_to_create:
        with transaction.atomic():
            TemperatureReading.objects.bulk_create(
                readings_to_create,
                ignore_conflicts=False,
                batch_size=batch_size
            )
    
    # Update file upload progress
    # FileUpload.objects.filter(id=file_upload_id).update(
    #     processed_rows=models.F('processed_rows') + processed_count,
    #     updated_at=timezone.now()
    # )
    
    # # Import models.F for the update
    # from django.db.models import F
    # FileUpload.objects.filter(id=file_upload_id).update(
    #     processed_rows=F('processed_rows') + processed_count
    # )
    # Update file upload progress
    FileUpload.objects.filter(id=file_upload_id).update(
        processed_rows=F('processed_rows') + processed_count
    )
    logger.debug(
        f"Chunk {chunk_number} completed: {processed_count} processed, {error_count} errors"
    )
    
    return {
        'chunk_number': chunk_number,
        'processed': processed_count,
        'errors': error_count,
        'cities': list(affected_cities)
    }


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def update_city_cache(self, city_id: str) -> Dict[str, Any]:
    """
    Update the temperature cache for a specific city.
    
    Args:
        city_id: City identifier
        
    Returns:
        Dictionary with cache update results
    """
    logger.debug(f"Updating cache for city {city_id}")
    
    try:
        city = City.objects.get(city_id=city_id)
    except City.DoesNotExist:
        logger.warning(f"City {city_id} not found for cache update")
        return {'error': f'City {city_id} not found'}
    
    # Get or create cache entry
    cache, created = CityTemperatureCache.objects.get_or_create(city=city)
    
    # Refresh cache with latest statistics
    cache.refresh()
    
    logger.info(
        f"Cache updated for city {city_id}: "
        f"mean={cache.mean_temperature}, max={cache.max_temperature}, min={cache.min_temperature}"
    )
    
    return {
        'city_id': city_id,
        'mean_temperature': float(cache.mean_temperature) if cache.mean_temperature else None,
        'max_temperature': float(cache.max_temperature) if cache.max_temperature else None,
        'min_temperature': float(cache.min_temperature) if cache.min_temperature else None,
        'reading_count': cache.reading_count
    }


@shared_task(bind=True)
def refresh_all_city_caches(self) -> Dict[str, Any]:
    """
    Refresh temperature caches for all cities.
    
    This task is scheduled to run periodically to ensure
    cache consistency.
    
    Returns:
        Dictionary with refresh results
    """
    logger.info("Starting cache refresh for all cities")
    
    cities = City.objects.all()
    updated_count = 0
    error_count = 0
    
    for city in cities:
        try:
            cache, created = CityTemperatureCache.objects.get_or_create(city=city)
            cache.refresh()
            updated_count += 1
        except Exception as e:
            logger.error(f"Error refreshing cache for city {city.city_id}: {str(e)}")
            error_count += 1
    
    logger.info(
        f"Cache refresh completed: {updated_count} updated, {error_count} errors"
    )
    
    return {
        'updated': updated_count,
        'errors': error_count,
        'total_cities': cities.count()
    }


@shared_task(bind=True)
def mark_stale_caches(self, city_ids: List[str]) -> Dict[str, Any]:
    """
    Mark caches as stale for the specified cities.
    
    This is called when new data is added to trigger
    background cache refresh.
    
    Args:
        city_ids: List of city identifiers
        
    Returns:
        Dictionary with results
    """
    updated = CityTemperatureCache.objects.filter(
        city__city_id__in=city_ids
    ).update(is_stale=True)
    
    return {'marked_stale': updated}
