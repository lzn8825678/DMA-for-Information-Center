from django.contrib import admin
from .models import ProcessTemplate, NodeTemplate, ProcessInstance, NodeInstance, Task, Binding

@admin.register(ProcessTemplate)
class ProcessTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_active",)

@admin.register(NodeTemplate)
class NodeTemplateAdmin(admin.ModelAdmin):
    list_display = ("process", "name", "code", "node_type", "order", "assigned_group_name", "assigned_user")
    list_filter = ("process", "node_type")
    search_fields = ("name", "code")
    ordering = ("process", "order")

@admin.register(ProcessInstance)
class ProcessInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "process", "starter", "status", "start_time", "end_time")
    list_filter = ("status", "process")
    search_fields = ("id", "process__name", "starter__username")

@admin.register(NodeInstance)
class NodeInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "process_instance", "node_template", "status", "arrived_at", "finished_at", "handler")
    list_filter = ("status", "node_template__process")
    search_fields = ("process_instance__id", "node_template__name")

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "assignee", "node_instance", "status", "created_at", "finished_at")
    list_filter = ("status",)
    search_fields = ("assignee__username",)

@admin.register(Binding)
class BindingAdmin(admin.ModelAdmin):
    list_display = ("process_instance", "content_type", "object_id")
    search_fields = ("process_instance__id",)
