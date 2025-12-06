from django.urls import path
from .views import (
    WebhookListView, WebhookCreateView, WebhookUpdateView, WebhookDeleteView,
    WebhookEndpointCreateView, WebhookEndpointDetailView, WebhookReceiverView,
    WebhookStreamView
)

urlpatterns = [
    path('', WebhookListView.as_view(), name='webhook_list'),
    path('create/', WebhookCreateView.as_view(), name='webhook_create'),
    path('update/<int:pk>/', WebhookUpdateView.as_view(), name='webhook_update'),
    path('delete/<int:pk>/', WebhookDeleteView.as_view(), name='webhook_delete'),
    path('tester/create/', WebhookEndpointCreateView.as_view(), name='webhook_endpoint_create'),
    path('tester/<uuid:token>/', WebhookEndpointDetailView.as_view(), name='webhook_endpoint_detail'),
    path('tester/<uuid:token>/stream/', WebhookStreamView.as_view(), name='webhook_stream'),
    path('inbound/<uuid:token>/', WebhookReceiverView.as_view(), name='webhook_receiver'),
]
