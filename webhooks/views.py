from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Webhook, WebhookEndpoint, WebhookRequest
from .forms import WebhookForm
import json

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

class WebhookEndpointCreateView(LoginRequiredMixin, View):
    def post(self, request):
        endpoint = WebhookEndpoint.objects.create(user=request.user)
        return JsonResponse({'url': request.build_absolute_uri(reverse('webhook_endpoint_detail', args=[endpoint.token]))})

class WebhookEndpointDetailView(LoginRequiredMixin, DetailView):
    model = WebhookEndpoint
    template_name = 'webhooks/endpoint_detail.html'
    context_object_name = 'endpoint'
    slug_field = 'token'
    slug_url_kwarg = 'token'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['test_url'] = self.request.build_absolute_uri(reverse('webhook_receiver', args=[self.object.token]))
        return context

@method_decorator(csrf_exempt, name='dispatch')
class WebhookReceiverView(View):
    def post(self, request, token):
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Received webhook request for token: {token}")
        
        endpoint = get_object_or_404(WebhookEndpoint, token=token)
        
        headers = dict(request.headers)
        try:
            body = request.body.decode('utf-8')
        except:
            body = '[Binary Data]'
            
        WebhookRequest.objects.create(
            endpoint=endpoint,
            headers=headers,
            body=body,
            method=request.method,
            query_params=request.GET.dict()
        )
        logger.info("Webhook request saved successfully.")
        return HttpResponse('OK')
