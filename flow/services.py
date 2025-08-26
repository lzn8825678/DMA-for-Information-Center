from __future__ import annotations
from typing import Any, Dict, List
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import (FlowTemplate, FlowNode, Transition, FlowInstance, WorkItem, WorkItemStatus, InstanceStatus, ActionLog)

U = get_user_model()

SAFE_BUILTINS = {
    'True': True,
    'False': False,
    'None': None,
    'len': len,
    'min': min,
    'max': max,
    'sum': sum,
    'any': any,
    'all': all,
}

def _eval_condition(expr: str, form: Dict[str, Any]) -> bool:
    if not expr:
        return True
    # 简易安全沙箱评估（仅内联变量 form），后续可替换为 asteval/numexpr
    env = {"__builtins__": SAFE_BUILTINS, 'form': form}
    try:
        return bool(eval(expr, env, {}))
    except Exception:
        return False

def _resolve_assignees(node: FlowNode, form: Dict[str, Any]) -> List[int]:
    """根据指派规则计算候选处理人（返回用户ID列表）。"""
    user_ids: set[int] = set()
    rules = node.assignees or []
    for r in rules:
        rtype = r.get('type')
        val = r.get('value')
        if rtype == 'user_ids' and isinstance(val, list):
            user_ids.update([int(x) for x in val])
        elif rtype == 'by_field' and isinstance(val, str):
            uid = form.get(val)
            if isinstance(uid, int):
                user_ids.add(uid)
        elif rtype == 'group_names' and isinstance(val, list):
            qs = U.objects.filter(groups__name__in=val).values_list('id', flat=True)
            user_ids.update(qs)
    return list(user_ids)

@transaction.atomic
def start_instance(template: FlowTemplate, starter: U, form_data: Dict[str, Any], title: str|None=None) -> FlowInstance:
    start_node = template.nodes.filter(type='start').first()
    if not start_node:
        raise ValueError('模板缺少开始节点')
    # 找到开始后的第一个可执行节点（经由无条件/满足条件的边）
    next_node = None
    for t in template.transitions.filter(source=start_node).order_by('priority', 'id'):
        if _eval_condition(t.condition, form_data):
            next_node = t.target
            break
    if not next_node:
        raise ValueError('开始节点没有可达的后续节点')

    ins = FlowInstance.objects.create(
        template=template,
        status=InstanceStatus.RUNNING,
        starter=starter,
        current_node=next_node,
        form_data=form_data,
        title=title or f"{template.name}-{starter}",
    )
    # 生成首个工作项
    assignees = _resolve_assignees(next_node, form_data)
    WorkItem.objects.create(instance=ins, node=next_node, assignees=assignees)
    ActionLog.objects.create(instance=ins, node=start_node, user=starter, action='start', payload={'form': form_data})
    return ins

@transaction.atomic
def submit_task(work_item: WorkItem, user: U, action: str, comment: str|None, new_form_data: Dict[str, Any]|None=None) -> FlowInstance:
    if work_item.status in (WorkItemStatus.DONE, WorkItemStatus.CANCELED):
        raise ValueError('工作项已完成或已取消')
    if work_item.owner and work_item.owner_id != user.id:
        raise PermissionError('非当前认领人')
    # 合并表单
    ins = work_item.instance
    form = ins.form_data.copy()
    if new_form_data:
        form.update(new_form_data)
    # 基于当前节点的连线挑选下一节点
    next_node = None
    for t in ins.template.transitions.filter(source=work_item.node).order_by('priority','id'):
        if _eval_condition(t.condition, form):
            next_node = t.target
            break


    # 完成当前工作项
    work_item.status = WorkItemStatus.DONE
    work_item.action = action
    work_item.comment = comment or ''
    work_item.owner = user
    work_item.save(update_fields=['status','action','comment','owner','updated_at'])


    ActionLog.objects.create(instance=ins, node=work_item.node, user=user, action=action, payload={'comment': comment or ''})


    # 到达结束？
    if next_node and next_node.type == 'end':
        ins.status = InstanceStatus.COMPLETED
        ins.current_node = None
        ins.form_data = form
        ins.save(update_fields=['status','current_node','form_data','updated_at'])
        ActionLog.objects.create(instance=ins, node=next_node, user=user, action='complete', payload={})
        return ins


    if not next_node:
        raise ValueError('没有满足条件的后续节点')


    ins.current_node = next_node
    ins.form_data = form
    ins.save(update_fields=['current_node','form_data','updated_at'])


    assignees = _resolve_assignees(next_node, form)
    WorkItem.objects.create(instance=ins, node=next_node, assignees=assignees)
    return ins

@transaction.atomic
def claim_work_item(work_item: WorkItem, user: U) -> WorkItem:
    if work_item.status != WorkItemStatus.OPEN:
        raise ValueError('工作项非可认领状态')
    if user.id not in (work_item.assignees or []):
        raise PermissionError('不在候选人列表')
    work_item.owner = user
    work_item.status = WorkItemStatus.CLAIMED
    work_item.save(update_fields=['owner','status','updated_at'])
    return work_item