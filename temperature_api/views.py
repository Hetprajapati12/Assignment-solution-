"""
API Views for Temperature Service.

Provides endpoints for:
- Temperature statistics retrieval
- File upload and processing
- User registration
- Processing status checking
"""

import os
import uuid
import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import City, TemperatureReading, CityTemperatureCache, FileUpload
from .serializers import (
    CitySerializer,
    CityTemperatureStatisticsSerializer,
    FileUploadSerializer,
    FileUploadRequestSerializer,
    UserRegistrationSerializer,
    TemperatureReadingSerializer,
)
from .tasks import process_temperature_file, update_city_cache

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """
    Health check endpoint for container orchestration.
    
    Returns service health status without authentication.
    """
    
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Return health status."""
        return Response({
            'status': 'healthy',
            'service': 'temperature-service',
            'version': '1.0.0'
        })


class UserRegistrationView(APIView):
    """
    User registration endpoint.
    
    Allows new users to register for API access.
    """
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """Register a new user."""
        serializer = UserRegistrationSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            logger.info(f"New user registered: {user.username}")
            return Response({
                'message': 'User registered successfully',
                'username': user.username,
                'email': user.email
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for City model.
    
    Provides list and retrieve operations for cities.
    """
    
    queryset = City.objects.all()
    serializer_class = CitySerializer
    lookup_field = 'city_id'
    
    @method_decorator(cache_page(60))  # Cache for 1 minute
    def list(self, request, *args, **kwargs):
        """List all cities with caching."""
        return super().list(request, *args, **kwargs)


class CityTemperatureStatisticsView(APIView):
    """
    API endpoint for retrieving temperature statistics for a city.
    
    GET /api/cities/{city_id}/statistics/
    
    Returns mean, max, and min temperature for the specified city.
    Uses caching for improved performance.
    """
    
    def get(self, request, city_id: str):
        """
        Retrieve temperature statistics for a city.
        
        Args:
            city_id: The city identifier
            
        Returns:
            Temperature statistics including mean, max, min temperatures
        """
        # First, try to get from cache
        try:
            city = City.objects.get(city_id=city_id)
        except City.DoesNotExist:
            return Response(
                {'error': f'City with id "{city_id}" not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Try to get cached statistics
        try:
            cache = CityTemperatureCache.objects.get(city=city)
            
            # Check if cache is stale
            if cache.is_stale:
                # Trigger async cache refresh
                update_city_cache.delay(city_id)
            
            serializer = CityTemperatureStatisticsSerializer(data={
                'city_id': city_id,
                'mean_temperature': float(cache.mean_temperature) if cache.mean_temperature else None,
                'max_temperature': float(cache.max_temperature) if cache.max_temperature else None,
                'min_temperature': float(cache.min_temperature) if cache.min_temperature else None,
                'reading_count': cache.reading_count,
                'last_updated': cache.last_updated,
                'cached': True
            })
            serializer.is_valid()
            
            return Response(serializer.data)
            
        except CityTemperatureCache.DoesNotExist:
            # Cache miss - calculate statistics directly
            stats = city.get_statistics()
            
            # Create cache entry asynchronously
            update_city_cache.delay(city_id)
            
            serializer = CityTemperatureStatisticsSerializer(data={
                'city_id': city_id,
                'mean_temperature': stats['mean_temperature'],
                'max_temperature': stats['max_temperature'],
                'min_temperature': stats['min_temperature'],
                'reading_count': stats['reading_count'],
                'cached': False
            })
            serializer.is_valid()
            
            return Response(serializer.data)


class FileUploadView(APIView):
    """
    API endpoint for uploading temperature data files.
    
    POST /api/upload/
    
    Accepts CSV files with temperature readings in format:
    city_id,temp,timestamp
    """
    
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """
        Upload a temperature data file for processing.
        
        The file is saved and processing is triggered asynchronously
        via Celery task queue.
        """
        serializer = FileUploadRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = serializer.validated_data['file']
        
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_id = uuid.uuid4()
        file_extension = os.path.splitext(uploaded_file.name)[1]
        unique_filename = f"{file_id}{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file to disk
        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        
        # Create FileUpload record
        file_upload = FileUpload.objects.create(
            id=file_id,
            filename=uploaded_file.name,
            file_path=file_path,
            file_size=uploaded_file.size,
            uploaded_by=request.user if request.user.is_authenticated else None
        )
        
        # Trigger async processing
        task = process_temperature_file.delay(str(file_upload.id))
        
        # Update task ID
        file_upload.celery_task_id = task.id
        file_upload.save(update_fields=['celery_task_id'])
        
        logger.info(
            f"File upload initiated: {file_upload.filename} "
            f"(ID: {file_upload.id}, Task: {task.id})"
        )
        
        return Response({
            'message': 'File uploaded successfully. Processing started.',
            'upload_id': str(file_upload.id),
            'task_id': task.id,
            'status_url': f'/api/upload/{file_upload.id}/status/'
        }, status=status.HTTP_202_ACCEPTED)


class FileUploadStatusView(APIView):
    """
    API endpoint for checking file upload processing status.
    
    GET /api/upload/{upload_id}/status/
    """
    
    def get(self, request, upload_id: str):
        """Get the processing status of an uploaded file."""
        try:
            file_upload = FileUpload.objects.get(id=upload_id)
        except (FileUpload.DoesNotExist, ValueError):
            return Response(
                {'error': 'File upload not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = FileUploadSerializer(file_upload)
        return Response(serializer.data)


class FileUploadListView(APIView):
    """
    API endpoint for listing file uploads.
    
    GET /api/uploads/
    """
    
    def get(self, request):
        """List all file uploads for the authenticated user."""
        if request.user.is_authenticated:
            uploads = FileUpload.objects.filter(uploaded_by=request.user)
        else:
            uploads = FileUpload.objects.none()
        
        # Allow admins to see all uploads
        if request.user.is_staff:
            uploads = FileUpload.objects.all()
        
        serializer = FileUploadSerializer(uploads[:100], many=True)
        return Response({
            'count': uploads.count(),
            'results': serializer.data
        })


class TemperatureReadingsView(APIView):
    """
    API endpoint for retrieving temperature readings for a city.
    
    GET /api/cities/{city_id}/readings/
    """
    
    def get(self, request, city_id: str):
        """
        Retrieve temperature readings for a city.
        
        Supports pagination via limit and offset query parameters.
        """
        try:
            city = City.objects.get(city_id=city_id)
        except City.DoesNotExist:
            return Response(
                {'error': f'City with id "{city_id}" not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Pagination parameters
        limit = min(int(request.query_params.get('limit', 100)), 1000)
        offset = int(request.query_params.get('offset', 0))
        
        # Optional date range filtering
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        readings = city.temperature_readings.all()
        
        if start_date:
            readings = readings.filter(timestamp__gte=start_date)
        if end_date:
            readings = readings.filter(timestamp__lte=end_date)
        
        total_count = readings.count()
        readings = readings[offset:offset + limit]
        
        serializer = TemperatureReadingSerializer(readings, many=True)
        
        return Response({
            'city_id': city_id,
            'total_count': total_count,
            'limit': limit,
            'offset': offset,
            'results': serializer.data
        })


class RefreshCacheView(APIView):
    """
    API endpoint to manually trigger cache refresh.
    
    POST /api/cities/{city_id}/refresh-cache/
    """
    
    def post(self, request, city_id: str):
        """Trigger cache refresh for a specific city."""
        try:
            city = City.objects.get(city_id=city_id)
        except City.DoesNotExist:
            return Response(
                {'error': f'City with id "{city_id}" not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Trigger async cache update
        task = update_city_cache.delay(city_id)
        
        return Response({
            'message': f'Cache refresh triggered for city {city_id}',
            'task_id': task.id
        }, status=status.HTTP_202_ACCEPTED)
