from typing import Optional, Sequence
from django.contrib.auth.models import Group
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from django.contrib.auth import get_user_model
from .models import (
    ProcessTemplate, NodeTemplate, ProcessInstance, NodeInstance, Task, Binding
)

User = get_user_model()

def _calc_assignees(node_tpl: NodeTemplate) -> Sequence[User]:
    """
    计算当前节点的处理人集合：优先指定用户，否则按组名取所有组内用户。
    """
    if node_tpl.assigned_user:
        return [node_tpl.assigned_user]
    if node_tpl.assigned_group_name:
        try:
            grp = Group.objects.get(name=node_tpl.assigned_group_name)
            return list(grp.user_set.all())
        except Group.DoesNotExist:
            return []
    return []

@transaction.atomic
def start_process(process_code: str, starter: User, biz_object, description: str = "") -> ProcessInstance:
    """
    发起流程并绑定到某个业务对象（biz_object）。
    """
    tpl = ProcessTemplate.objects.get(code=process_code, is_active=True)
    # 取 start 节点
    start_node_tpl = tpl.nodes.filter(node_type="start").order_by("order").first()
    if not start_node_tpl:
        raise ValueError("流程缺少开始节点")

    # 创建流程实例
    inst = ProcessInstance.objects.create(process=tpl, starter=starter, status="running")

    # 绑定业务对象
    ct = ContentType.objects.get_for_model(biz_object.__class__)
    Binding.objects.create(process_instance=inst, content_type=ct, object_id=biz_object.pk)

    # 创建 start 节点实例并自动完成，推进到下一个节点（第一个审批节点）
    start_node_inst = NodeInstance.objects.create(
        process_instance=inst, node_template=start_node_tpl, status="done", handler=starter, finished_at=timezone.now()
    )

    # 下一个审批节点
    next_node_tpl = tpl.nodes.filter(order__gt=start_node_tpl.order).order_by("order").first()
    if not next_node_tpl:
        # 没有下个节点，直接结束
        inst.status = "finished"
        inst.current_node = None
        inst.end_time = timezone.now()
        inst.save(update_fields=["status", "current_node", "end_time"])
        return inst

    # 生成审批节点实例与任务
    next_node_inst = NodeInstance.objects.create(process_instance=inst, node_template=next_node_tpl, status="pending")
    inst.current_node = next_node_inst
    inst.save(update_fields=["current_node"])

    for u in _calc_assignees(next_node_tpl):
        Task.objects.create(node_instance=next_node_inst, assignee=u)

    return inst

@transaction.atomic
def approve_task(task_id: int, user: User, comment: str = "") -> ProcessInstance:
    """
    审批通过当前任务，推进到下一个节点；若没有下一个节点则结束流程。
    """
    task = Task.objects.select_related("node_instance", "node_instance__process_instance", "node_instance__node_template").get(id=task_id)
    if task.assignee_id != user.id or task.status != "open":
        raise PermissionError("无权处理此任务或任务已关闭")

    # 完成本任务 & 节点
    task.status = "closed"
    task.finished_at = timezone.now()
    task.save(update_fields=["status", "finished_at"])

    node_inst = task.node_instance
    node_inst.status = "done"
    node_inst.handler = user
    node_inst.finished_at = timezone.now()
    node_inst.save(update_fields=["status", "handler", "finished_at"])

    inst = node_inst.process_instance
    tpl = node_inst.node_template.process

    # 找下一个节点
    next_node_tpl = tpl.nodes.filter(order__gt=node_inst.node_template.order).order_by("order").first()
    if not next_node_tpl:
        inst.status = "finished"
        inst.current_node = None
        inst.end_time = timezone.now()
        inst.save(update_fields=["status", "current_node", "end_time"])
        return inst

    # 创建下个节点实例 & 任务
    next_node_inst = NodeInstance.objects.create(process_instance=inst, node_template=next_node_tpl, status="pending")
    inst.current_node = next_node_inst
    inst.save(update_fields=["current_node"])

    for u in _calc_assignees(next_node_tpl):
        Task.objects.create(node_instance=next_node_inst, assignee=u)

    return inst

@transaction.atomic
def reject_task(task_id: int, user: User, comment: str = "") -> ProcessInstance:
    """
    MVP 的简单驳回：直接将流程结束为 'canceled'（后续再做回退到上一步/任意节点）。
    """
    task = Task.objects.select_related("node_instance", "node_instance__process_instance").get(id=task_id)
    if task.assignee_id != user.id or task.status != "open":
        raise PermissionError("无权处理此任务或任务已关闭")

    task.status = "closed"
    task.finished_at = timezone.now()
    task.save(update_fields=["status", "finished_at"])

    node_inst = task.node_instance
    node_inst.status = "done"
    node_inst.handler = user
    node_inst.finished_at = timezone.now()
    node_inst.save(update_fields=["status", "handler", "finished_at"])

    inst = node_inst.process_instance
    inst.status = "canceled"
    inst.current_node = None
    inst.end_time = timezone.now()
    inst.save(update_fields=["status", "current_node", "end_time"])
    return inst

def get_binding_instance(biz_object) -> Optional[ProcessInstance]:
    """
    查询某业务对象是否已经绑定流程实例。
    """
    ct = ContentType.objects.get_for_model(biz_object.__class__)
    try:
        b = Binding.objects.select_related("process_instance").get(content_type=ct, object_id=biz_object.pk)
        return b.process_instance
    except Binding.DoesNotExist:
        return None
