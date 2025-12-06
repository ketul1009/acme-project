from django.db import models
from django.contrib.auth.models import User
import uuid

class Webhook(models.Model):
    EVENT_CHOICES = [
        ('product.created', 'Product Created'),
        ('product.updated', 'Product Updated'),
        ('product.deleted', 'Product Deleted'),
        ('import.completed', 'Import Completed'),
        ('bulk_delete.completed', 'Bulk Delete Completed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='webhooks')
    url = models.URLField()
    events = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.url}"

class WebhookEndpoint(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='webhook_endpoints')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.token)

class WebhookRequest(models.Model):
    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name='requests')
    headers = models.JSONField()
    body = models.TextField()
    method = models.CharField(max_length=10)
    query_params = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.method} - {self.created_at}"
