import os
from django.shortcuts import render
from django.http import JsonResponse
from django.views.generic import ListView, TemplateView, View
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.conf import settings
from .models import Product
from .tasks import process_csv_import, delete_all_products

class ProductListView(ListView):
    model = Product
    template_name = 'products/list.html'
    context_object_name = 'products'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(sku__icontains=query) | queryset.filter(name__icontains=query)
        return queryset.order_by('-created_at')

class ProductUploadView(TemplateView):
    template_name = 'products/upload.html'

    def post(self, request, *args, **kwargs):
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'No file uploaded'}, status=400)
        
        file = request.FILES['file']
        if not file.name.endswith('.csv'):
            return JsonResponse({'error': 'Invalid file type. Please upload a CSV.'}, status=400)

        # Save file temporarily
        file_path = default_storage.save(f'tmp/{file.name}', file)
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        # Trigger Celery task
        task = process_csv_import.delay(full_path)
        
        return JsonResponse({'task_id': task.id})

class UploadProgressView(View):
    def get(self, request, task_id):
        cache_key = f'import_progress_{task_id}'
        progress_data = cache.get(cache_key)
        
        if not progress_data:
            # If task is pending or just started and not yet in cache
            return JsonResponse({'status': 'pending', 'progress': 0, 'message': 'Initializing...'})
        
        return JsonResponse(progress_data)

class BulkDeleteView(View):
    def post(self, request):
        task = delete_all_products.delay()
        return JsonResponse({'task_id': task.id})

class DeleteProgressView(View):
    def get(self, request, task_id):
        cache_key = f'delete_progress_{task_id}'
        progress_data = cache.get(cache_key)
        
        if not progress_data:
            return JsonResponse({'status': 'pending', 'progress': 0, 'message': 'Initializing...'})
        
        return JsonResponse(progress_data)

class ProductCreateView(View):
    def post(self, request):
        sku = request.POST.get('sku')
        name = request.POST.get('name')
        description = request.POST.get('description')
        is_active = request.POST.get('is_active') == 'on'

        if Product.objects.filter(sku=sku).exists():
            return JsonResponse({'error': 'SKU already exists'}, status=400)

        product = Product.objects.create(
            sku=sku,
            name=name,
            description=description,
            is_active=is_active
        )
        return JsonResponse({'message': 'Product created successfully', 'id': product.id})

class ProductUpdateView(View):
    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)

        # Handle JSON data for inline editing
        import json
        data = json.loads(request.body)
        
        new_sku = data.get('sku', product.sku)
        if new_sku != product.sku:
            if Product.objects.filter(sku=new_sku).exclude(pk=pk).exists():
                return JsonResponse({'error': 'SKU already exists'}, status=400)
            product.sku = new_sku

        product.name = data.get('name', product.name)
        product.description = data.get('description', product.description)
        product.is_active = data.get('is_active', product.is_active)
        product.save()
        
        return JsonResponse({'message': 'Product updated successfully'})

class ProductDeleteView(View):
    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
            product.delete()
            return JsonResponse({'message': 'Product deleted successfully'})
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)
