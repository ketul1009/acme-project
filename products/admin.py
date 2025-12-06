from django.contrib import admin
from .models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'is_active', 'created_at', 'updated_at')
    search_fields = ('sku', 'name')
    list_filter = ('is_active', 'created_at')
    ordering = ('-created_at',)
