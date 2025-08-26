"""
URL configuration for Task_Django project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from users import views as user_views
from tasks import views as task_views
from digitization import views as digi_views
from users import views as user_views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
# from filebox import views

urlpatterns = [
    path('register/', user_views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('tasks/', task_views.task_list, name='task_list'),
    path('tasks/add/', task_views.add_task, name='add_task'),
    path('tasks/complete/<int:task_id>/', task_views.complete_task, name='complete_task'),
    path('tasks/export/', task_views.export_tasks, name='tasks_export'),
    path('projects/', task_views.project_list, name='project_list'),
    path('projects/<int:proj_id>/', task_views.project_detail, name='project_detail'),
    path('outbound/add/', digi_views.add_outbound, name='add_outbound'),
    path('outbound/list/', digi_views.outbound_list, name='outbound_list'),
    path('outbound/<int:out_id>/claim/', digi_views.claim_outbound, name='claim_outbound'),
    path('workorder/<int:out_id>/edit/', digi_views.edit_workorder, name='edit_workorder'),
    path('quality/pending/', digi_views.pending_quality_list, name='pending_quality_list'),
    path('quality/<int:wo_id>/check/', digi_views.check_quality, name='check_quality'),
    path('dashboard/', user_views.dashboard, name='dashboard'),
    path('admin/', admin.site.urls),
    path('filebox/', include('filebox.urls')),
    path('outbound/export/', digi_views.export_full_report, name='export_full_report'),
    path('return/list/', digi_views.return_list, name='return_list'),
    path('return/confirm/<int:out_id>/', digi_views.confirm_return, name='confirm_return'),
    path('return/finished/', digi_views.returned_list, name='returned_list'),
    path('return/finished/export/', digi_views.export_returned_csv, name='export_returned_csv'),
    path('return/detail/<int:out_id>/', digi_views.return_detail, name='return_detail'),
    path('attendance/', include('attendance.urls')),
    path('relicmap/', include('relicmap.urls')),
    path("flow/", include("flow.urls")),

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
