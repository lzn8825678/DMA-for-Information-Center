# flow/views.py
from __future__ import annotations
from typing import Any, Dict, List

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import FlowTemplateForm
from .models import FlowTemplate, WorkItem
from .services import start_instance, submit_task, claim_work_item, release_work_item
from .utils import merge_overrides, schema_properties

def _schema_properties(schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return schema_properties(schema)

def _build_fields_from_schema(schema: Dict[str, Any], current_data: Dict[str, Any] | None = None,
                              overrides: Dict[str, set]|None=None) -> List[Dict[str, Any]]:
    current_data = current_data or {}
    ov = overrides or {"hidden": set(), "readonly": set(), "required": set()}
    fields: List[Dict[str, Any]] = []
    props = _schema_properties(schema)
    for key, meta in props.items():
        if key in ov["hidden"]:
            continue  # 后端不渲染隐藏字段
        title = meta.get("title") or key
        ftype = meta.get("type") or "string"
        enum = meta.get("enum") if isinstance(meta.get("enum"), list) else None

        # 简单映射
        if enum:
            html_type = "select"
        elif ftype in ("integer", "number"):
            html_type = "number"
        elif ftype == "boolean":
            html_type = "checkbox"
        else:
            html_type = "text"

        fields.append(
            {
                "name": key,
                "title": title,
                "html_type": html_type,
                "enum": enum,
                "value": current_data.get(key, "" if html_type != "checkbox" else False),
                "required": key in ov["required"],
                "readonly": key in ov["readonly"],
            }
        )
    return fields


@login_required
def template_list(request: HttpRequest) -> HttpResponse:
    qs = FlowTemplate.objects.all().order_by("-updated_at")
    return render(request, "flow/template_list.html", {"items": qs})


@login_required
@require_http_methods(["GET", "POST"])
def template_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = FlowTemplateForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.creator = request.user
            obj.save()
            messages.success(request, "模板已创建，请在后台配置节点与连线。")
            return redirect("flow_template_list")
    else:
        form = FlowTemplateForm()
    return render(request, "flow/template_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def instance_start(request: HttpRequest, template_code: str) -> HttpResponse:
    tpl = get_object_or_404(FlowTemplate, code=template_code, status="active")
    schema = tpl.form.json_schema or {}
    # 发起时不套用覆盖（起始由模板定义必填）
    fields = _build_fields_from_schema(schema)

    if request.method == "POST":
        form_data: Dict[str, Any] = request.POST.dict()
        form_data.pop("csrfmiddlewaretoken", None)
        title = request.POST.get("title") or tpl.name
        # checkbox 兜底
        for f in fields:
            if f["html_type"] == "checkbox":
                form_data[f["name"]] = request.POST.get(f["name"]) == "on"
        ins = start_instance(tpl, request.user, form_data, title=title)
        messages.success(request, f"流程已发起：实例 #{ins.id}")
        return redirect("flow_work_inbox")

    return render(request, "flow/instance_start.html", {"tpl": tpl, "fields": fields})


@login_required
def work_inbox(request: HttpRequest) -> HttpResponse:
    uid = request.user.id
    items = (
        WorkItem.objects.filter(status__in=["open", "claimed"])
        .filter(Q(owner_id=uid) | Q(assignees__contains=[uid]))
        .select_related("instance", "node", "node__template")
        .order_by("-updated_at")
    )
    return render(request, "flow/work_inbox.html", {"items": items})


@login_required
@require_http_methods(["GET", "POST"])
def work_submit(request: HttpRequest, pk: int) -> HttpResponse:
    wi = get_object_or_404(
        WorkItem.objects.select_related("instance", "node", "instance__template", "instance__template__form"),
        pk=pk,
    )
    instance = wi.instance
    tpl = instance.template
    schema = tpl.form.json_schema or {}

    # 读节点覆盖
    overrides = merge_overrides(schema, wi.node.form_overrides)
    fields = _build_fields_from_schema(schema, current_data=instance.form_data or {}, overrides=overrides)

    if request.method == "POST":
        action = request.POST.get("action") or "submit"
        comment = request.POST.get("comment") or ""
        payload = {}
        for f in fields:
            # 后端已不渲染 hidden；只读字段仍从请求忽略
            if f["readonly"]:
                continue
            name = f["name"]
            if f["html_type"] == "checkbox":
                payload[name] = request.POST.get(name) == "on"
            else:
                payload[name] = request.POST.get(name, "")
        submit_task(wi, request.user, action, comment, new_form_data=payload)
        messages.success(request, "已提交")
        return redirect("flow_work_inbox")

    return render(
        request,
        "flow/work_submit.html",
        {
            "wi": wi,
            "fields": fields,
            "instance": instance,
            "tpl": tpl,
        },
    )


# 认领 / 释放
@login_required
def work_claim(request: HttpRequest, pk: int) -> HttpResponse:
    wi = get_object_or_404(WorkItem, pk=pk)
    claim_work_item(wi, request.user)
    messages.success(request, "已认领")
    return redirect("flow_work_inbox")

@login_required
def work_release(request: HttpRequest, pk: int) -> HttpResponse:
    wi = get_object_or_404(WorkItem, pk=pk)
    release_work_item(wi, request.user)
    messages.success(request, "已释放")
    return redirect("flow_work_inbox")
