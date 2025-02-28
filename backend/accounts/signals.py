# In accounts/signals.py (create this file)
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import CustomUser, RadioStation
import logging

logger = logging.getLogger('accounts')

@receiver(post_save, sender=CustomUser)
def user_saved(sender, instance, created, **kwargs):
    """Log when users are created or modified"""
    if created:
        logger.info(f"New user created: {instance.email} (Type: {instance.user_type})")
    else:
        logger.info(f"User updated: {instance.email}")

@receiver(post_save, sender=RadioStation)
def station_saved(sender, instance, created, **kwargs):
    """Log when stations are created or modified"""
    if created:
        logger.info(f"New radio station created: {instance.name}")
    else:
        logger.info(f"Radio station updated: {instance.name}")