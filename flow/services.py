from __future__ import annotations
from typing import Any, Dict, List
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import (FlowTemplate, FlowNode, Transition, FlowInstance, WorkItem, WorkItemStatus, InstanceStatus, ActionLog)
from .utils import safe_eval, merge_overrides, validate_form, schema_properties, normalize_types

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

def _eval_condition(expr: str, form: Dict[str, Any], action: str|None=None) -> bool:
    # 使用安全表达式，允许引用 form[...] 和 action
    ctx = {"form": form, "action": action}
    try:
        return safe_eval(expr, ctx)
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

    # 1) 基于模板主表单进行校验（开始节点不考虑 readonly/hidden，仅校验 schema.required）
    schema = template.form.json_schema or {}
    props = schema_properties(schema)
    form_data = normalize_types(props, form_data)
    overrides = merge_overrides(schema, {})  # 发起时不使用节点覆盖
    ok, errs = validate_form(schema, overrides, form_data)
    if not ok:
        raise ValueError("表单校验失败: " + "；".join(errs))

    # 2) 决定下一节点
    next_node = None
    for t in template.transitions.filter(source=start_node).order_by('priority', 'id'):
        if _eval_condition(t.condition, form_data, action="start"):
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

    assignees = _resolve_assignees(next_node, form_data)
    WorkItem.objects.create(instance=ins, node=next_node, assignees=assignees)
    ActionLog.objects.create(instance=ins, node=start_node, user=starter, action='start', payload={'form': form_data})
    return ins

@transaction.atomic
def submit_task(work_item: WorkItem, user: U, action: str, comment: str|None, new_form_data: Dict[str, Any]|None=None) -> FlowInstance:
    if work_item.status in (WorkItemStatus.DONE, WorkItemStatus.CANCELED):
        raise ValueError('工作项已完成或已取消')

    # 权限：owner 或 候选人（认领模式由前端/接口控制）
    uid = user.id
    if work_item.owner_id and work_item.owner_id != uid:
        raise PermissionError('非当前认领人')
    if not work_item.owner_id and uid not in (work_item.assignees or []):
        raise PermissionError('不在候选人列表')

    ins = work_item.instance
    tpl = ins.template
    node = work_item.node

    # 合并表单
    schema = tpl.form.json_schema or {}
    props = schema_properties(schema)
    overrides = merge_overrides(schema, node.form_overrides)

    old_form = ins.form_data.copy()
    new_data = (new_form_data or {}).copy()

    # 后端兜底：隐藏字段不可提交
    for h in overrides["hidden"]:
        new_data.pop(h, None)

    # 只读字段不可被修改（若提交了，与旧值不一致则报错）
    for r in overrides["readonly"]:
        if r in new_data and r in old_form and new_data[r] != old_form[r]:
            raise ValueError(f"字段“{r}”为只读，不能修改")

    # 类型规范化 + 校验（必填、枚举等）
    merged = old_form.copy()
    merged.update(new_data)
    merged = normalize_types(props, merged)

    ok, errs = validate_form(schema, overrides, merged)
    if not ok:
        raise ValueError("表单校验失败: " + "；".join(errs))

    # 选择下一节点：允许条件表达式引用当前 action
    next_node = None
    for t in tpl.transitions.filter(source=node).order_by('priority', 'id'):
        if _eval_condition(t.condition, merged, action=action):
            next_node = t.target
            break

    # 完成当前工作项
    work_item.status = WorkItemStatus.DONE
    work_item.action = action or 'submit'
    work_item.comment = comment or ''
    work_item.owner = user
    work_item.save(update_fields=['status','action','comment','owner','updated_at'])

    ActionLog.objects.create(instance=ins, node=node, user=user, action=work_item.action, payload={'comment': work_item.comment})

    if not next_node:
        raise ValueError('没有满足条件的后续节点')

    # 结束
    if next_node.type == 'end':
        ins.status = InstanceStatus.COMPLETED
        ins.current_node = None
        ins.form_data = merged
        ins.save(update_fields=['status','current_node','form_data','updated_at'])
        ActionLog.objects.create(instance=ins, node=next_node, user=user, action='complete', payload={})
        return ins

    # 正常流转
    ins.current_node = next_node
    ins.form_data = merged
    ins.save(update_fields=['current_node','form_data','updated_at'])

    assignees = _resolve_assignees(next_node, merged)
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

@transaction.atomic
def release_work_item(work_item: WorkItem, user: U) -> WorkItem:
    if work_item.owner_id != user.id:
        raise PermissionError('只有当前认领人可以释放')
    if work_item.status not in (WorkItemStatus.CLAIMED, WorkItemStatus.OPEN):
        raise ValueError('当前状态不可释放')
    work_item.owner = None
    work_item.status = WorkItemStatus.OPEN
    work_item.save(update_fields=['owner','status','updated_at'])
    return work_item