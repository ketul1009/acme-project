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

from products.models import Product

class WebhookEndpointCreateView(LoginRequiredMixin, View):
    def post(self, request):
        # Check if user already has an endpoint
        endpoint = WebhookEndpoint.objects.filter(user=request.user).order_by('-created_at').first()
        if not endpoint:
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
        # Add latest 3 products for testing
        context['products'] = Product.objects.filter(user=self.request.user).order_by('-updated_at')[:3]
        return context

from django.http import StreamingHttpResponse
import redis
from django.conf import settings

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
            
        webhook_request = WebhookRequest.objects.create(
            endpoint=endpoint,
            headers=headers,
            body=body,
            method=request.method,
            query_params=request.GET.dict()
        )
        logger.info("Webhook request saved successfully.")

        # Publish to Redis
        try:
            r = redis.from_url(settings.REDIS_URL)
            # Create HTML fragment matching the Accordion structure
            import json
            headers_pretty = json.dumps(webhook_request.headers, indent=2)
            query_pretty = json.dumps(webhook_request.query_params, indent=2)
            
            html = f"""
            <div class="accordion-item">
                <h2 class="accordion-header" id="heading{webhook_request.id}">
                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse"
                        data-bs-target="#collapse{webhook_request.id}">
                        <span class="badge bg-primary me-2">{webhook_request.method}</span>
                        {webhook_request.created_at.strftime('%Y-%m-%d %H:%M:%S')}
                    </button>
                </h2>
                <div id="collapse{webhook_request.id}" class="accordion-collapse collapse" data-bs-parent="#requestsAccordion">
                    <div class="accordion-body">
                        <h5>Headers</h5>
                        <pre class="bg-light p-2 rounded"><code>{headers_pretty}</code></pre>

                        <h5>Query Params</h5>
                        <pre class="bg-light p-2 rounded"><code>{query_pretty}</code></pre>

                        <h5>Body</h5>
                        <pre class="bg-light p-2 rounded"><code>{webhook_request.body}</code></pre>
                    </div>
                </div>
            </div>
            """
            
            # SSE requires data to be single line or each line prefixed with data:
            # We'll just remove newlines for simplicity
            html = html.replace('\n', '').strip()
            
            r.publish(f'webhook_stream_{token}', html)
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {e}")

        return HttpResponse('OK')

class WebhookStreamView(LoginRequiredMixin, View):
    def get(self, request, token):
        print(f"DEBUG: Stream connected for token {token}")
        def event_stream():
            r = redis.from_url(settings.REDIS_URL)
            pubsub = r.pubsub()
            pubsub.subscribe(f'webhook_stream_{token}')
            
            for message in pubsub.listen():
                if message['type'] == 'message':
                    data = message['data'].decode('utf-8')
                    yield f"data: {data}\n\n"
                    
        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'  # Disable buffering in Nginx/Fly
        return response
