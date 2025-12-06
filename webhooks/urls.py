from django.urls import path
from .views import WebhookListView, WebhookCreateView, WebhookUpdateView, WebhookDeleteView

urlpatterns = [
    path('', WebhookListView.as_view(), name='webhook_list'),
    path('create/', WebhookCreateView.as_view(), name='webhook_create'),
    path('update/<int:pk>/', WebhookUpdateView.as_view(), name='webhook_update'),
    path('delete/<int:pk>/', WebhookDeleteView.as_view(), name='webhook_delete'),
]
