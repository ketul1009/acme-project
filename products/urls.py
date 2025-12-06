from django.urls import path
from .views import (
    ProductListView, ProductUploadView, ProductCreateView, 
    ProductUpdateView, ProductDeleteView, BulkDeleteView,
    UploadProgressView, DeleteProgressView, ActiveOperationView,
    OperationListView
)

urlpatterns = [
    path('', ProductListView.as_view(), name='product_list'),
    path('upload/', ProductUploadView.as_view(), name='product_upload'),
    path('upload/progress/<str:task_id>/', UploadProgressView.as_view(), name='upload_progress'),
    path('active-operation/', ActiveOperationView.as_view(), name='active_operation'),
    path('create/', ProductCreateView.as_view(), name='product_create'),
    path('<int:pk>/update/', ProductUpdateView.as_view(), name='product_update'),
    path('<int:pk>/delete/', ProductDeleteView.as_view(), name='product_delete'),
    path('delete-all/', BulkDeleteView.as_view(), name='product_delete_all'),
    path('delete/progress/<str:task_id>/', DeleteProgressView.as_view(), name='delete_progress'),
    path('operations/', OperationListView.as_view(), name='operation_list'),
]
