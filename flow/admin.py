# flow/admin.py
from __future__ import annotations
from typing import List, Tuple

from django import forms
from django.contrib import admin

from .models import (
    FormDef, FormField, FlowTemplate, FlowNode, NodeFieldRule,
    Transition, FlowInstance, WorkItem, ActionLog
)

# ----- 表单字段内联 -----
class FormFieldInline(admin.TabularInline):
    model = FormField
    extra = 0
    fields = ('order', 'name', 'title', 'type', 'required', 'options')
    ordering = ('order', 'id')
    classes = ('collapse',)  # 可视化更干净，想展开可去掉

@admin.register(FormDef)
class FormDefAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    inlines = [FormFieldInline]


# ----- 工具：从 FormDef 取字段 choices -----
def field_choices(tpl: FlowTemplate) -> List[Tuple[str, str]]:
    try:
        return [(f.name, f.title or f.name) for f in tpl.form_def.fields.all()]
    except Exception:
        return []


# ----- 节点里的“字段权限规则”内联 -----
class NodeFieldRuleForm(forms.ModelForm):
    class Meta:
        model = NodeFieldRule
        fields = ('field_name', 'hidden', 'readonly', 'required')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        node = getattr(self.instance, 'node', None)
        tpl = node.template if node else None
        self.fields['field_name'] = forms.ChoiceField(
            choices=field_choices(tpl) if tpl else [],
            required=True, label='字段名',
            help_text='从表单字段中选择'
        )

class NodeFieldRuleInline(admin.TabularInline):
    model = NodeFieldRule
    form = NodeFieldRuleForm
    extra = 0


@admin.register(FlowNode)
class FlowNodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'template', 'code', 'name', 'type', 'allow_claim')
    list_filter = ('type', 'template')
    search_fields = ('code', 'name', 'template__code', 'template__name')
    filter_horizontal = ('assigned_users', 'assigned_departments')

    fieldsets = (
        (None, {'fields': (('template', 'code', 'name', 'type'), 'allow_claim',
                           ('assigned_users', 'assigned_departments'))}),
        ('兼容旧 JSON（不用再维护）', {'classes': ('collapse',),
                           'fields': ('assignees', 'form_overrides')}),
    )

    inlines = [NodeFieldRuleInline]


@admin.register(FlowTemplate)
class FlowTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name', 'status', 'version', 'updated_at')
    list_filter = ('status',)
    search_fields = ('code', 'name')
    # 这里显示 form_def，而不是旧的 form
    fields = ('code', 'name', 'description', 'form_def', 'status', 'version')


@admin.register(Transition)
class TransitionAdmin(admin.ModelAdmin):
    list_display = ('id', 'template', 'source', 'target', 'name', 'priority')
    list_filter = ('template',)
    search_fields = ('name', 'template__code', 'template__name')


@admin.register(FlowInstance)
class FlowInstanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'template', 'title', 'status', 'starter', 'current_node', 'updated_at')
    list_filter = ('status', 'template')
    search_fields = ('title',)


@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'instance', 'node', 'status', 'owner', 'updated_at')
    list_filter = ('status', 'node__template')
    search_fields = ('instance__title',)


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'instance', 'node', 'user', 'action', 'created_at')
    list_filter = ('action', 'node__template')
    search_fields = ('remark',)
