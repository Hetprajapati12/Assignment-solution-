"""
URL routing for Temperature API.

Provides routes for:
- City operations
- Temperature statistics
- File uploads
- User registration
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    HealthCheckView,
    UserRegistrationView,
    CityViewSet,
    CityTemperatureStatisticsView,
    FileUploadView,
    FileUploadStatusView,
    FileUploadListView,
    TemperatureReadingsView,
    RefreshCacheView,
)

# Create router for viewsets
router = DefaultRouter()
router.register(r'cities', CityViewSet, basename='city')

urlpatterns = [
    # Health check (no auth required)
    path('health/', HealthCheckView.as_view(), name='health-check'),
    
    # User registration (no auth required)
    path('auth/register/', UserRegistrationView.as_view(), name='user-register'),
    
    # Router URLs (cities list and detail)
    path('', include(router.urls)),
    
    # City temperature statistics
    path(
        'cities/<str:city_id>/statistics/',
        CityTemperatureStatisticsView.as_view(),
        name='city-statistics'
    ),
    
    # City temperature readings
    path(
        'cities/<str:city_id>/readings/',
        TemperatureReadingsView.as_view(),
        name='city-readings'
    ),
    
    # Cache refresh
    path(
        'cities/<str:city_id>/refresh-cache/',
        RefreshCacheView.as_view(),
        name='city-refresh-cache'
    ),
    
    # File upload endpoints
    path('upload/', FileUploadView.as_view(), name='file-upload'),
    path('uploads/', FileUploadListView.as_view(), name='file-upload-list'),
    path(
        'upload/<str:upload_id>/status/',
        FileUploadStatusView.as_view(),
        name='file-upload-status'
    ),
]
