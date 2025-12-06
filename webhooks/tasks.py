import requests
import logging
from celery import shared_task
from .models import Webhook

logger = logging.getLogger(__name__)

@shared_task
def send_webhook_notification(user_id, event_type, payload):
    # Filter webhooks that are active AND have the event_type in their events list
    webhooks = Webhook.objects.filter(user_id=user_id, is_active=True)
    
    data = {
        'event': event_type,
        'payload': payload
    }
    
    for webhook in webhooks:
        # Check if event is subscribed
        if event_type not in webhook.events:
            continue
            
        try:
            response = requests.post(webhook.url, json=data, timeout=5)
            response.raise_for_status()
            logger.info(f"Webhook sent to {webhook.url} for event {event_type}")
        except requests.RequestException as e:
            logger.error(f"Failed to send webhook to {webhook.url}: {str(e)}")
