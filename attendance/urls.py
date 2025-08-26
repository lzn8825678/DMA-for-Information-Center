from django.urls import path
from . import views

urlpatterns = [
    path('', views.attendance_list, name='attendance_list'),
    path('add/', views.attendance_add, name='attendance_add'),
    path('export/', views.export_attendance_csv, name='export_attendance_csv'),
]
