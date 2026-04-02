from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Subscription

@receiver(post_save, sender=User)
def create_subscription(sender, instance, created, **kwargs):
    """Automatically create a free subscription when user is created"""
    if created:
        Subscription.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_subscription(sender, instance, **kwargs):
    """Save subscription when user is saved"""
    instance.subscription.save()
