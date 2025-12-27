"""
Django signals for Temperature API.

Provides automatic cache invalidation when temperature readings are updated.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import TemperatureReading, CityTemperatureCache


@receiver(post_save, sender=TemperatureReading)
def mark_cache_stale_on_save(sender, instance, created, **kwargs):
    """Mark city cache as stale when a new reading is saved."""
    if created:
        try:
            cache = CityTemperatureCache.objects.get(city=instance.city)
            if not cache.is_stale:
                cache.is_stale = True
                cache.save(update_fields=['is_stale'])
        except CityTemperatureCache.DoesNotExist:
            pass


@receiver(post_delete, sender=TemperatureReading)
def mark_cache_stale_on_delete(sender, instance, **kwargs):
    """Mark city cache as stale when a reading is deleted."""
    try:
        cache = CityTemperatureCache.objects.get(city=instance.city)
        if not cache.is_stale:
            cache.is_stale = True
            cache.save(update_fields=['is_stale'])
    except CityTemperatureCache.DoesNotExist:
        pass
