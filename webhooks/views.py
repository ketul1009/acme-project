from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Webhook
from .forms import WebhookForm

class WebhookListView(LoginRequiredMixin, ListView):
    model = Webhook
    template_name = 'webhooks/list.html'
    context_object_name = 'webhooks'

    def get_queryset(self):
        return Webhook.objects.filter(user=self.request.user).order_by('-created_at')

class WebhookCreateView(LoginRequiredMixin, CreateView):
    model = Webhook
    form_class = WebhookForm
    template_name = 'webhooks/form.html'
    success_url = reverse_lazy('webhook_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class WebhookUpdateView(LoginRequiredMixin, UpdateView):
    model = Webhook
    form_class = WebhookForm
    template_name = 'webhooks/form.html'
    success_url = reverse_lazy('webhook_list')

    def get_queryset(self):
        return Webhook.objects.filter(user=self.request.user)

class WebhookDeleteView(LoginRequiredMixin, DeleteView):
    model = Webhook
    success_url = reverse_lazy('webhook_list')

    def get_queryset(self):
        return Webhook.objects.filter(user=self.request.user)
