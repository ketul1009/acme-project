import csv
import time
import os
import logging
from celery import shared_task

logger = logging.getLogger(__name__)
from django.core.cache import cache
from .models import Product

@shared_task(bind=True)
def process_csv_import(self, file_path):
    task_id = self.request.id
    cache_key = f'import_progress_{task_id}'
    
    # Initialize progress
    cache.set(cache_key, {'status': 'processing', 'progress': 0, 'message': 'Starting import...'}, timeout=3600)

    try:
        file_size = os.path.getsize(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            # Wrapper to track bytes read
            processed_bytes = 0
            def progress_wrapper(file_obj):
                nonlocal processed_bytes
                for line in file_obj:
                    processed_bytes += len(line.encode('utf-8'))
                    yield line

            reader = csv.DictReader(progress_wrapper(f))
            
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
                
                # Update progress periodically (every 1000 rows or when flushing)
                if rows_read % 1000 == 0:
                    progress = int((processed_bytes / file_size) * 100) if file_size > 0 else 0
                    cache.set(cache_key, {'status': 'processing', 'progress': progress, 'message': f'Processed {rows_read} records...'}, timeout=3600)

            # Process remaining
            if chunk_map:
                _process_chunk(list(chunk_map.values()))


            cache.set(cache_key, {'status': 'complete', 'progress': 100, 'message': 'Import complete!'}, timeout=3600)
            
    except Exception as e:
        cache.set(cache_key, {'status': 'failed', 'progress': 0, 'message': str(e)}, timeout=3600)
        logger.error(f"Error processing CSV import: {str(e)}")

def _process_chunk(chunk):
    # Upsert logic using bulk_create with conflict handling
    Product.objects.bulk_create(
        chunk,
        update_conflicts=True,
        unique_fields=['sku'],
        update_fields=['name', 'description', 'is_active', 'updated_at']
    )
