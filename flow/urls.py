from django.urls import path
from . import views

app_name = "flow"

urlpatterns = [
    path("tasks/", views.my_tasks, name="my_tasks"),
    path("tasks/<int:task_id>/approve/", views.do_approve, name="approve"),
    path("tasks/<int:task_id>/reject/", views.do_reject, name="reject"),
]
