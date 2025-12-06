import os
from django.shortcuts import render
from django.http import JsonResponse
from django.views.generic import ListView, TemplateView, View
from django.core.files.storage import default_storage, FileSystemStorage
from django.core.cache import cache
from django.conf import settings
from .models import Product
from .tasks import process_csv_import, delete_all_products

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views.generic import CreateView
from webhooks.tasks import send_webhook_notification

class SignUpView(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy('login')
    template_name = 'registration/signup.html'

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'products/list.html'
    context_object_name = 'products'
    paginate_by = 10

    def get_queryset(self):
        queryset = Product.objects.filter(user=self.request.user).order_by('-created_at')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(sku__icontains=query) | queryset.filter(name__icontains=query)
        return queryset

class ProductUploadView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'products/upload.html')

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'error': 'No file uploaded'}, status=400)
        
        if not file.name.endswith('.csv'):
            return JsonResponse({'error': 'Invalid file format. Please upload a CSV file.'}, status=400)

        # Save file using default storage (S3 in prod, local in dev)
        filename = default_storage.save(file.name, file)
        
        # Trigger Celery task with filename
        task = process_csv_import.delay(filename, request.user.id)
        
        return JsonResponse({'task_id': task.id})

class UploadProgressView(LoginRequiredMixin, View):
    def get(self, request, task_id):
        cache_key = f'import_progress_{task_id}'
        progress_data = cache.get(cache_key)
        
        if not progress_data:
            # If task is pending or just started and not yet in cache
            return JsonResponse({'status': 'pending', 'progress': 0, 'message': 'Initializing...'})
        
        return JsonResponse(progress_data)

class BulkDeleteView(LoginRequiredMixin, View):
    def post(self, request):
        task = delete_all_products.delay(request.user.id)
        return JsonResponse({'task_id': task.id})

class DeleteProgressView(LoginRequiredMixin, View):
    def get(self, request, task_id):
        cache_key = f'delete_progress_{task_id}'
        progress_data = cache.get(cache_key)
        
        if not progress_data:
            return JsonResponse({'status': 'pending', 'progress': 0, 'message': 'Initializing...'})
        
        return JsonResponse(progress_data)

class ProductCreateView(LoginRequiredMixin, View):
    def post(self, request):
        sku = request.POST.get('sku')
        name = request.POST.get('name')
        description = request.POST.get('description')
        is_active = request.POST.get('is_active') == 'on'
        print(request.user)
        if Product.objects.filter(sku=sku, user=request.user).exists():
            return JsonResponse({'error': 'SKU already exists'}, status=400)

        product = Product.objects.create(
            user=request.user,
            sku=sku,
            name=name,
            description=description,
            is_active=is_active
        )
        send_webhook_notification.delay(request.user.id, 'product.created', {'sku': sku, 'name': name})
        return JsonResponse({'message': 'Product created successfully', 'id': product.id})

class ProductUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, user=request.user)
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)

        # Handle JSON data for inline editing
        import json
        data = json.loads(request.body)
        
        new_sku = data.get('sku', product.sku)
        if new_sku != product.sku:
            if Product.objects.filter(sku=new_sku, user=request.user).exclude(pk=pk).exists():
                return JsonResponse({'error': 'SKU already exists'}, status=400)
            product.sku = new_sku

        product.name = data.get('name', product.name)
        product.description = data.get('description', product.description)
        product.is_active = data.get('is_active', product.is_active)
        product.save()
        
        send_webhook_notification.delay(request.user.id, 'product.updated', {'sku': product.sku, 'name': product.name})
        return JsonResponse({'message': 'Product updated successfully'})

class ProductDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, user=request.user)
            sku = product.sku
            product.delete()
            send_webhook_notification.delay(request.user.id, 'product.deleted', {'sku': sku})
            return JsonResponse({'message': 'Product deleted successfully'})
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)
