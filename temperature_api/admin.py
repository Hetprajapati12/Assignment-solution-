"""
Django Admin configuration for Temperature API.

Provides admin interface for managing:
- Cities
- Temperature readings
- Cache entries
- File uploads
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import City, TemperatureReading, CityTemperatureCache, FileUpload


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    """Admin configuration for City model."""
    
    list_display = ['city_id', 'name', 'reading_count', 'created_at', 'updated_at']
    search_fields = ['city_id', 'name']
    list_filter = ['created_at']
    ordering = ['city_id']
    readonly_fields = ['created_at', 'updated_at']
    
    def reading_count(self, obj):
        """Get the count of temperature readings for this city."""
        return obj.temperature_readings.count()
    
    reading_count.short_description = 'Readings'


@admin.register(TemperatureReading)
class TemperatureReadingAdmin(admin.ModelAdmin):
    """Admin configuration for TemperatureReading model."""
    
    list_display = ['city', 'temperature', 'timestamp', 'created_at']
    list_filter = ['city', 'timestamp', 'created_at']
    search_fields = ['city__city_id']
    ordering = ['-timestamp']
    readonly_fields = ['created_at']
    raw_id_fields = ['city']
    date_hierarchy = 'timestamp'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('city')


@admin.register(CityTemperatureCache)
class CityTemperatureCacheAdmin(admin.ModelAdmin):
    """Admin configuration for CityTemperatureCache model."""
    
    list_display = [
        'city', 'mean_temperature', 'max_temperature',
        'min_temperature', 'reading_count', 'is_stale', 'last_updated'
    ]
    list_filter = ['is_stale', 'last_updated']
    search_fields = ['city__city_id']
    readonly_fields = ['last_updated']
    
    actions = ['refresh_selected_caches']
    
    def refresh_selected_caches(self, request, queryset):
        """Refresh cache for selected cities."""
        for cache in queryset:
            cache.refresh()
        self.message_user(request, f"Refreshed {queryset.count()} cache entries.")
    
    refresh_selected_caches.short_description = "Refresh selected caches"


@admin.register(FileUpload)
class FileUploadAdmin(admin.ModelAdmin):
    """Admin configuration for FileUpload model."""
    
    list_display = [
        'filename', 'status_badge', 'file_size_display',
        'progress', 'error_count', 'uploaded_by', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'uploaded_by']
    search_fields = ['filename', 'id', 'celery_task_id']
    readonly_fields = [
        'id', 'file_size', 'total_rows', 'processed_rows',
        'error_count', 'error_messages', 'celery_task_id',
        'retry_count', 'created_at', 'updated_at', 'completed_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('File Information', {
            'fields': ('id', 'filename', 'file_path', 'file_size')
        }),
        ('Processing Status', {
            'fields': (
                'status', 'total_rows', 'processed_rows',
                'error_count', 'retry_count'
            )
        }),
        ('Task Information', {
            'fields': ('celery_task_id',)
        }),
        ('Errors', {
            'fields': ('error_messages',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at', 'uploaded_by')
        }),
    )
    
    def status_badge(self, obj):
        """Display status as a colored badge."""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'partial': 'purple'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    
    status_badge.short_description = 'Status'
    
    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    file_size_display.short_description = 'Size'
    
    def progress(self, obj):
        """Display processing progress as a percentage."""
        pct = obj.progress_percentage
        return format_html(
            '<progress value="{}" max="100" style="width: 100px;"></progress> {}%',
            pct,
            pct
        )
    
    progress.short_description = 'Progress'


# Customize admin site header
admin.site.site_header = "Temperature Service Administration"
admin.site.site_title = "Temperature Service"
admin.site.index_title = "Welcome to Temperature Service Admin"
