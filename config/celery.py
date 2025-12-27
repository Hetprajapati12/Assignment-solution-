"""
Celery configuration for Temperature Service.

This module configures Celery for distributed task processing,
specifically for handling large file uploads asynchronously.
"""

import os
from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Create the Celery application
app = Celery('temperature_service')

# Configure Celery using Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Configure task routing for different priorities
app.conf.task_routes = {
    'temperature_api.tasks.process_temperature_file': {'queue': 'file_processing'},
    'temperature_api.tasks.process_file_chunk': {'queue': 'chunk_processing'},
    'temperature_api.tasks.update_city_cache': {'queue': 'cache_updates'},
    'temperature_api.tasks.refresh_all_city_caches': {'queue': 'cache_updates'},
}

# Configure task priorities
app.conf.task_default_priority = 5
app.conf.task_queue_max_priority = 10

# Configure error handling
app.conf.task_annotations = {
    'temperature_api.tasks.process_temperature_file': {
        'rate_limit': '10/m',  # Limit file processing rate
        'max_retries': 3,
    },
    'temperature_api.tasks.process_file_chunk': {
        'rate_limit': '100/m',  # Higher rate for chunk processing
        'max_retries': 5,
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    print(f'Request: {self.request!r}')
