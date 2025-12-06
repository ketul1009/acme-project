import csv
import time
import os
import logging
from celery import shared_task

logger = logging.getLogger(__name__)
from django.core.cache import cache
from .models import Product

from webhooks.tasks import send_webhook_notification
import io
from django.core.files.storage import default_storage

from .models import Product, BulkOperation

# ...

@shared_task(bind=True)
def process_csv_import(self, operation_id):
    task_id = self.request.id
    cache_key = f'import_progress_{task_id}'
    
    # Initialize progress in Cache
    cache.set(cache_key, {'status': 'processing', 'progress': 0, 'message': 'Starting import...'}, timeout=3600)

    try:
        # Update DB Status -> Processing
        operation = BulkOperation.objects.get(pk=operation_id)
        operation.status = 'processing'
        operation.save()
        
        user_id = operation.user_id
        filename = operation.input_file.name

        file_size = default_storage.size(filename)
        
        with default_storage.open(filename, 'rb') as f:
            text_file = io.TextIOWrapper(f, encoding='utf-8')
            
            # Wrapper to track bytes read
            processed_bytes = 0
            def progress_wrapper(file_obj):
                nonlocal processed_bytes
                for line in file_obj:
                    processed_bytes += len(line.encode('utf-8'))
                    yield line

            reader = csv.DictReader(progress_wrapper(text_file))
            
            chunk_size = 5000
            chunk_map = {}
            rows_read = 0
            
            for row in reader:
                sku = row.get('sku', '').strip()
                name = row.get('name', '').strip()
                description = row.get('description', '').strip()
                
                if not sku:
                    continue
                
                sku = sku.lower()
                
                product = Product(
                    user_id=user_id,
                    sku=sku,
                    name=name,
                    description=description,
                    is_active=True
                )
                # Deduplicate within chunk: overwrite existing SKU with latest version
                chunk_map[sku] = product
                rows_read += 1

                # Flush if chunk is full
                if len(chunk_map) >= chunk_size:
                    _process_chunk(list(chunk_map.values()))
                    chunk_map = {}
                
                # Update progress in Cache only
                if rows_read % 1000 == 0:
                    progress = int((processed_bytes / file_size) * 100) if file_size > 0 else 0
                    cache.set(cache_key, {'status': 'processing', 'progress': progress, 'message': f'Processed {rows_read} records...'}, timeout=3600)

            # Process remaining
            if chunk_map:
                _process_chunk(list(chunk_map.values()))

            # Update Cache -> Complete
            cache.set(cache_key, {'status': 'complete', 'progress': 100, 'message': 'Import complete!'}, timeout=3600)
            
            # Update DB Status -> Completed
            operation.status = 'completed'
            operation.save()
            
            # Trigger Webhook
            send_webhook_notification.delay(user_id, 'import.completed', {'rows_processed': rows_read})
            
    except Exception as e:
        logger.error(f"Error processing CSV import: {str(e)}")
        cache.set(cache_key, {'status': 'failed', 'progress': 0, 'message': str(e)}, timeout=3600)
        
        if 'operation' in locals():
            operation.status = 'failed'
            operation.save()

def _process_chunk(chunk):
    # Upsert logic using bulk_create with conflict handling
    Product.objects.bulk_create(
        chunk,
        update_conflicts=True,
        unique_fields=['user', 'sku'],
        update_fields=['name', 'description', 'is_active', 'updated_at']
    )

@shared_task(bind=True)
def delete_all_products(self, operation_id):
    task_id = self.request.id
    cache_key = f'delete_progress_{task_id}'
    
    try:
        # Update DB Status -> Processing
        operation = BulkOperation.objects.get(pk=operation_id)
        operation.status = 'processing'
        operation.save()
        
        user_id = operation.user_id
        
        total_count = Product.objects.filter(user_id=user_id).count()
        cache.set(cache_key, {'status': 'processing', 'progress': 0, 'message': f'Starting deletion of {total_count} products...'}, timeout=3600)

        deleted_count = 0
        batch_size = 5000
        
        while True:
            # Get IDs to delete (using iterator to avoid loading all objects)
            ids = list(Product.objects.filter(user_id=user_id).values_list('pk', flat=True)[:batch_size])
            if not ids:
                break
            
            Product.objects.filter(pk__in=ids).delete()
            deleted_count += len(ids)
            
            progress = int((deleted_count / total_count) * 100) if total_count > 0 else 100
            
            # Update Cache only
            cache.set(cache_key, {'status': 'processing', 'progress': progress, 'message': f'Deleted {deleted_count} of {total_count} products...'}, timeout=3600)
            
        # Update Cache -> Complete
        cache.set(cache_key, {'status': 'complete', 'progress': 100, 'message': 'Deletion complete!'}, timeout=3600)
        
        # Update DB Status -> Completed
        operation.status = 'completed'
        operation.save()
        
        # Trigger Webhook
        send_webhook_notification.delay(user_id, 'bulk_delete.completed', {'deleted_count': deleted_count})

    except Exception as e:
        logger.error(f"Error deleting products: {str(e)}")
        cache.set(cache_key, {'status': 'failed', 'progress': 0, 'message': str(e)}, timeout=3600)
        
        if 'operation' in locals():
            operation.status = 'failed'
            operation.save()
        raise e
