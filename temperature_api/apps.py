"""
Temperature API application configuration.
"""

from django.apps import AppConfig


class TemperatureApiConfig(AppConfig):
    """Configuration for the Temperature API application."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'temperature_api'
    verbose_name = 'Temperature API'

    def ready(self):
        """Perform initialization when the app is ready."""
        # Import signal handlers
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
