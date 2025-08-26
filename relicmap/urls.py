from django.urls import path
from . import views

urlpatterns = [
    path('', views.relic_dashboard, name='relic_dashboard'),
    path('detail/<int:pk>/', views.relic_detail, name='relic_detail'),
    path('logs/<int:pk>/', views.relic_logs, name='relic_logs'),
    path('add/', views.add_location, name='add_location'),
]
