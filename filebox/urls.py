from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_file, name='upload_file'),
    path('list/', views.file_list, name='file_list'),
    path('delete/<int:file_id>/', views.delete_file, name='delete_file'),
    path('categories/', views.manage_categories, name='manage_categories'),
    path('categories/delete/<int:category_id>/', views.delete_category, name='delete_category'),
]
