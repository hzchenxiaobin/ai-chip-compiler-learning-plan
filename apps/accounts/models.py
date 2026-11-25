"""账号 Profile 模型（设计文档 §8.2：必要偏好和删除状态）。"""
from django.conf import settings as dj_settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(
        dj_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    preferences = models.JSONField(default=dict, blank=True)
    marked_for_deletion_at = models.DateTimeField(null=True, blank=True)
    deletion_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"profile({self.user_id})"

    def preference(self, key: str, default=None):
        value = self.preferences.get(key, default)
        return default if value is None else value


@receiver(post_save, sender=dj_settings.AUTH_USER_MODEL)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
