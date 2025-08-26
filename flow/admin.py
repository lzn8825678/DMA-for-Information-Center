from django.contrib import admin
from .models import FormSchema, FlowTemplate, FlowNode, Transition, FlowInstance, WorkItem, ActionLog

@admin.register(FormSchema)
class FormSchemaAdmin(admin.ModelAdmin):
    list_display = ('id','name','updated_at')
    search_fields = ('name',)


class FlowNodeInline(admin.TabularInline):
    model = FlowNode
    extra = 0


class TransitionInline(admin.TabularInline):
    model = Transition
    fk_name = 'template'
    extra = 0

@admin.register(FlowTemplate)
class FlowTemplateAdmin(admin.ModelAdmin):
    list_display = ('id','code','name','status','version','updated_at')
    list_filter = ('status',)
    search_fields = ('code','name')
    inlines = [FlowNodeInline, TransitionInline]


@admin.register(FlowInstance)
class FlowInstanceAdmin(admin.ModelAdmin):
    list_display = ('id','template','title','status','starter','current_node','updated_at')
    list_filter = ('status','template')
    search_fields = ('title',)


@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = ('id','instance','node','status','owner','updated_at')
    list_filter = ('status','node__template')
    search_fields = ('instance__title',)


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ('id','instance','node','user','action','created_at')
    list_filter = ('action','node__template')
    search_fields = ('remark',)