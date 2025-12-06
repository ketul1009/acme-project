import os
from django.shortcuts import render
from django.http import JsonResponse
from django.views.generic import ListView, TemplateView, View
from django.core.files.storage import default_storage, FileSystemStorage
from django.core.cache import cache
from django.conf import settings
from .models import Product, BulkOperation
from .tasks import process_csv_import, delete_all_products

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views.generic import CreateView
from webhooks.tasks import send_webhook_notification
import json

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
        # Check for active operations
        if BulkOperation.objects.filter(
            user=request.user, 
            status__in=['pending', 'processing']
        ).exists():
            return JsonResponse({'error': 'An operation is already in progress.'}, status=400)

        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'error': 'No file uploaded'}, status=400)
        
        if not file.name.endswith('.csv'):
            return JsonResponse({'error': 'Invalid file format. Please upload a CSV file.'}, status=400)

        # Create BulkOperation
        operation = BulkOperation.objects.create(
            user=request.user,
            operation_type='import',
            input_file=file,
            status='pending'
        )
        
        # Trigger Celery task with operation_id
        task = process_csv_import.delay(operation.id)
        
        operation.task_id = task.id
        operation.save()
        
        return JsonResponse({'task_id': task.id, 'operation_id': operation.id})

class UploadProgressView(LoginRequiredMixin, View):
    def get(self, request, task_id):
        cache_key = f'import_progress_{task_id}'
        progress_data = cache.get(cache_key)
        
        if not progress_data:
            return JsonResponse({'status': 'pending', 'progress': 0, 'message': 'Initializing...'})
        
        return JsonResponse(progress_data)

class ActiveOperationView(LoginRequiredMixin, View):
    def get(self, request):
        operation = BulkOperation.objects.filter(
            user=request.user,
            status__in=['pending', 'processing']
        ).first()
        
        if operation:
            return JsonResponse({
                'active': True,
                'task_id': operation.task_id,
                'operation_type': operation.operation_type,
                'status': operation.status
            })
        return JsonResponse({'active': False})

class OperationListView(LoginRequiredMixin, ListView):
    model = BulkOperation
    template_name = 'products/operation_list.html'
    context_object_name = 'operations'
    paginate_by = 10

    def get_queryset(self):
        return BulkOperation.objects.filter(user=self.request.user)

class BulkDeleteView(LoginRequiredMixin, View):
    def post(self, request):
        if BulkOperation.objects.filter(
            user=request.user, 
            status__in=['pending', 'processing']
        ).exists():
            return JsonResponse({'error': 'An operation is already in progress.'}, status=400)

        operation = BulkOperation.objects.create(
            user=request.user,
            operation_type='delete',
            status='pending'
        )

        task = delete_all_products.delay(operation.id)
        
        operation.task_id = task.id
        operation.save()

        return JsonResponse({'task_id': task.id, 'operation_id': operation.id})

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
