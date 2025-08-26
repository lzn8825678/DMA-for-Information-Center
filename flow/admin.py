# flow/admin.py
from __future__ import annotations
from typing import List, Tuple

from django import forms
from django.contrib import admin

from .models import (
    FormSchema, FlowTemplate, FlowNode, NodeFieldRule, Transition,
    FlowInstance, WorkItem, ActionLog
)

# ---- 工具：从模板主表单里提取字段 choices ----
def schema_field_choices(tpl: FlowTemplate) -> List[Tuple[str,str]]:
    try:
        schema = tpl.form.json_schema or {}
        props = schema.get("properties") or {}
        if not isinstance(props, dict):
            return []
        return [(k, (props[k].get("title") or k)) for k in props.keys()]
    except Exception:
        return []


# ---- Inline：字段权限可视化规则 ----
class NodeFieldRuleForm(forms.ModelForm):
    class Meta:
        model = NodeFieldRule
        fields = ["field_name", "hidden", "readonly", "required"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        node: FlowNode | None = getattr(self, "instance", None) and self.instance.node or None
        tpl = node.template if node else None
        if tpl:
            self.fields["field_name"] = forms.ChoiceField(
                choices=schema_field_choices(tpl), required=True, label="字段名"
            )
        else:
            # 新增第一条规则时还没保存 node，提示用户先保存节点再加规则
            self.fields["field_name"] = forms.ChoiceField(
                choices=[], required=True, label="字段名",
                help_text="请先保存节点，再添加字段规则。"
            )

class NodeFieldRuleInline(admin.TabularInline):
    model = NodeFieldRule
    form = NodeFieldRuleForm
    extra = 0


@admin.register(FlowNode)
class FlowNodeAdmin(admin.ModelAdmin):
    list_display = ("id", "template", "code", "name", "type", "allow_claim")
    list_filter = ("type", "template")
    search_fields = ("code", "name", "template__code", "template__name")
    filter_horizontal = ("assigned_users", "assigned_departments")  # ✅ 双栏多选，更方便

    inlines = [NodeFieldRuleInline]

    fieldsets = (
        (None, {
            "fields": (
                ("template", "code", "name", "type"),
                "allow_claim",
                ("assigned_users", "assigned_departments"),
            )
        }),
        ("兼容旧版 JSON（可留空）", {
            "classes": ("collapse",),
            "fields": ("assignees", "form_overrides"),
            "description": "旧数据兼容用；新配置已使用可视化选择，无需再编辑 JSON。"
        }),
    )


@admin.register(FlowTemplate)
class FlowTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "status", "version", "updated_at")
    list_filter = ("status",)
    search_fields = ("code", "name")


@admin.register(FormSchema)
class FormSchemaAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "updated_at")
    search_fields = ("name",)


@admin.register(Transition)
class TransitionAdmin(admin.ModelAdmin):
    list_display = ("id", "template", "source", "target", "name", "priority")
    list_filter = ("template",)
    search_fields = ("name", "template__code", "template__name")


@admin.register(FlowInstance)
class FlowInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "template", "title", "status", "starter", "current_node", "updated_at")
    list_filter = ("status", "template")
    search_fields = ("title",)


@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = ("id", "instance", "node", "status", "owner", "updated_at")
    list_filter = ("status", "node__template")
    search_fields = ("instance__title",)


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ("id", "instance", "node", "user", "action", "created_at")
    list_filter = ("action", "node__template")
    search_fields = ("remark",)
