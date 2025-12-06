from django.urls import path
from .views import ProductListView, ProductUploadView, UploadProgressView, BulkDeleteView, ProductCreateView, ProductUpdateView, ProductDeleteView, DeleteProgressView

urlpatterns = [
    path('', ProductListView.as_view(), name='product_list'),
    path('upload/', ProductUploadView.as_view(), name='product_upload'),
    path('upload/progress/<str:task_id>/', UploadProgressView.as_view(), name='upload_progress'),
    path('delete-all/', BulkDeleteView.as_view(), name='bulk_delete'),
    path('delete/progress/<str:task_id>/', DeleteProgressView.as_view(), name='delete_progress'),
    path('create/', ProductCreateView.as_view(), name='product_create'),
    path('update/<int:pk>/', ProductUpdateView.as_view(), name='product_update'),
    path('delete/<int:pk>/', ProductDeleteView.as_view(), name='product_delete'),
]
