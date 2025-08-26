from django.urls import path
from . import views

app_name = "flow"

urlpatterns = [
    path('templates/', views.template_list, name='flow_template_list'),
    path('templates/new/', views.template_create, name='flow_template_create'),
    path('instances/start/<slug:template_code>/', views.instance_start, name='flow_instance_start'),
    path('work/inbox/', views.work_inbox, name='flow_work_inbox'),
    path('work/<int:pk>/submit/', views.work_submit, name='flow_work_submit'),
]
