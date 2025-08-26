from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Task
from .services import approve_task, reject_task

@login_required
def my_tasks(request):
    qs = Task.objects.select_related("node_instance", "node_instance__process_instance").filter(
        assignee=request.user, status="open"
    ).order_by("-created_at")
    return render(request, "flow/my_tasks.html", {"tasks": qs})

@login_required
def do_approve(request, task_id: int):
    if request.method == "POST":
        try:
            approve_task(task_id, request.user, comment=request.POST.get("comment",""))
            messages.success(request, "已审批通过")
        except Exception as e:
            messages.error(request, f"操作失败：{e}")
    return redirect("flow:my_tasks")

@login_required
def do_reject(request, task_id: int):
    if request.method == "POST":
        try:
            reject_task(task_id, request.user, comment=request.POST.get("comment",""))
            messages.success(request, "已驳回（流程结束）")
        except Exception as e:
            messages.error(request, f"操作失败：{e}")
    return redirect("flow:my_tasks")
