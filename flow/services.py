from __future__ import annotations
from typing import Any, Dict, List
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import (FlowTemplate, FlowNode, Transition, FlowInstance, WorkItem, WorkItemStatus, InstanceStatus, ActionLog)
from .utils import safe_eval, merge_overrides, validate_form, schema_properties, normalize_types
from django.db.models import Q
from .models import FormField, FieldType

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

def _fields_dict(form_def) -> dict:
    """把 FormField 列表转成 {name: FormField} 的 dict"""
    return {f.name: f for f in form_def.fields.all()}

def _normalize_and_validate(fields_map: dict, data: dict, required_extra: set[str]|None=None) -> tuple[dict, list[str]]:
    """
    根据字段定义做类型规范化+必填校验；返回 (规范化后的data, 错误列表)
    required_extra: 节点层面的额外必填（来自 NodeFieldRule）
    """
    errs = []
    out = dict(data)
    req = set(name for name, f in fields_map.items() if f.required)
    if required_extra:
        req |= set(required_extra)

    for name, f in fields_map.items():
        v = out.get(name, None)
        # 必填检查
        if name in req and (v is None or v == ''):
            errs.append(f'字段“{f.title or name}”为必填')
            continue

        # 规范化类型
        if v in (None, ''):
            continue
        try:
            if f.type == FieldType.INTEGER:
                out[name] = int(v)
            elif f.type == FieldType.NUMBER:
                out[name] = float(v)
            elif f.type == FieldType.BOOLEAN:
                if isinstance(v, bool): pass
                elif str(v).lower() in ('true','1','yes','on'):
                    out[name] = True
                elif str(v).lower() in ('false','0','no','off'):
                    out[name] = False
            elif f.type == FieldType.SELECT:
                if v not in f.enum_list():
                    errs.append(f'字段“{f.title or name}”必须是下拉选项之一')
            # TEXT/STRING/DATE/DATETIME 暂不强校验，后续可加格式校验
        except Exception:
            errs.append(f'字段“{f.title or name}”类型不正确')
    return out, errs
# def _overrides_from_rules(node, schema):
#     """
#     返回 dict: {"hidden": set(), "readonly": set(), "required": set()}
#     优先使用 NodeFieldRule；若该节点没有任何规则，则回落到旧 JSON form_overrides（兼容期）。
#     """
#     rules = list(node.field_rules.all())
#     if rules:
#         res = {"hidden": set(), "readonly": set(), "required": set()}
#         for r in rules:
#             if r.hidden:
#                 res["hidden"].add(r.field_name)
#             if r.readonly:
#                 res["readonly"].add(r.field_name)
#             if r.required:
#                 res["required"].add(r.field_name)
#         return res
#     # 回落旧 JSON（兼容以前的 form_overrides）
#     return merge_overrides(schema, node.form_overrides)
# def _eval_condition(expr: str, form: Dict[str, Any], action: str|None=None) -> bool:
#     # 使用安全表达式，允许引用 form[...] 和 action
#     ctx = {"form": form, "action": action}
#     try:
#         return safe_eval(expr, ctx)
#     except Exception:
#         return False

def _overrides_from_rules(node, schema=None):
    """
    优先使用 NodeFieldRule 生成 overrides；
    如果该节点没有任何规则，则回落旧 JSON (node.form_overrides)。
    返回结构: {"hidden": set(), "readonly": set(), "required": set()}
    """
    try:
        rules = list(node.field_rules.all())
    except Exception:
        rules = []

    if rules:
        res = {"hidden": set(), "readonly": set(), "required": set()}
        for r in rules:
            if r.hidden:
                res["hidden"].add(r.field_name)
            if r.readonly:
                res["readonly"].add(r.field_name)
            if r.required:
                res["required"].add(r.field_name)
        return res

    # 兼容旧 JSON；若你已弃用旧 JSON，可以直接 return {"hidden": set(), "readonly": set(), "required": set()}
    return merge_overrides(schema or {}, getattr(node, "form_overrides", {}) or {})

def _resolve_assignees(node, form):
    """
    返回用户ID列表。优先使用新字段 assigned_users/assigned_departments；
    若都为空，则回落到旧 JSON assignees（兼容期）。
    """
    user_ids = set()

    # ✅ 新：直接读关系
    if node.assigned_users.exists() or node.assigned_departments.exists():
        if node.assigned_users.exists():
            user_ids.update(node.assigned_users.values_list("id", flat=True))

        if node.assigned_departments.exists():
            # 假设用户模型有 department 外键
            dept_ids = list(node.assigned_departments.values_list("id", flat=True))
            user_ids.update(
                U.objects.filter(department_id__in=dept_ids).values_list("id", flat=True)
            )
        return list(user_ids)

    # ⬇️ 旧：回落 JSON（如还没迁移完）
    rules = node.assignees or []
    for r in rules:
        rtype = r.get('type')
        val = r.get('value')
        if rtype == 'user_ids' and isinstance(val, list):
            user_ids.update(int(x) for x in val)
        elif rtype == 'by_field' and isinstance(val, str):
            uid = form.get(val)
            if isinstance(uid, int):
                user_ids.add(uid)
        elif rtype == 'group_names' and isinstance(val, list):
            qs = U.objects.filter(groups__name__in=val).values_list('id', flat=True)
            user_ids.update(qs)
        elif rtype in ('dept_ids','dept_names'):
            # 如果历史 JSON 里有科室信息，也做一次兼容性解析（可按需扩展）
            pass
    return list(user_ids)

@transaction.atomic
def start_instance(template: FlowTemplate, starter: U, form_data: Dict[str, Any], title: str|None=None) -> FlowInstance:
    start_node = template.nodes.filter(type='start').first()
    if not start_node:
        raise ValueError('模板缺少开始节点')

    # 1) 基于模板主表单进行校验（开始节点不考虑 readonly/hidden，仅校验 schema.required）
    form_def = template.form_def
    fields_map = _fields_dict(form_def)

    # 先按“表单级”必填校验（发起阶段不套用节点覆盖）
    form_data, errs = _normalize_and_validate(fields_map, form_data)
    if errs:
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
def submit_task(work_item: WorkItem, user: U, action: str, comment: str | None, new_form_data: Dict[str, Any] | None = None) -> FlowInstance:
    """
    新版 submit：
    - 表单来源：FlowTemplate.form_def 下的 FormField（完全摆脱 JSON Schema）
    - 字段权限：优先 NodeFieldRule（隐藏/只读/必填），无规则时回落旧 JSON（兼容）
    - 类型与必填校验：基于 FormField.type/required + 节点额外必填（overrides.required）
    """
    # 0) 基本状态/权限检查
    if work_item.status in (WorkItemStatus.DONE, WorkItemStatus.CANCELED):
        raise ValueError('工作项已完成或已取消')

    uid = user.id
    if work_item.owner_id and work_item.owner_id != uid:
        raise PermissionError('非当前认领人')
    if not work_item.owner_id and uid not in (work_item.assignees or []):
        raise PermissionError('不在候选人列表')

    # 1) 取实例/模板/节点/表单定义
    ins = work_item.instance
    tpl = ins.template
    node = work_item.node
    form_def = tpl.form_def  # ✅ 新：使用结构化表单定义
    fields_map = _fields_dict(form_def)  # {field_name: FormField}

    # 2) 计算字段覆盖（隐藏/只读/必填）
    overrides = _overrides_from_rules(node, None)
    old_form = ins.form_data.copy()
    new_data = (new_form_data or {}).copy()

    # 2.1 隐藏字段后端兜底：不接受客户端提交的隐藏字段
    for h in overrides["hidden"]:
        new_data.pop(h, None)

    # 2.2 只读字段：如果提交值与旧值不一致，拒绝
    for r in overrides["readonly"]:
        if r in new_data and r in old_form and new_data[r] != old_form[r]:
            raise ValueError(f"字段“{r}”为只读，不能修改")

    # 3) 合并数据（旧值 + 新提交）
    merged = old_form.copy()
    merged.update(new_data)

    # 4) 规范化与校验（表单字段本身的 required + 节点覆盖的 required）
    merged, errs = _normalize_and_validate(fields_map, merged, required_extra=overrides["required"])
    if errs:
        raise ValueError("表单校验失败: " + "；".join(errs))

    # 5) 选择下一节点（条件可使用 form[...] 与 action）
    next_node = None
    for t in tpl.transitions.filter(source=node).order_by('priority', 'id'):
        if _eval_condition(t.condition, merged, action=(action or 'submit')):
            next_node = t.target
            break
    if not next_node:
        raise ValueError('没有满足条件的后续节点')

    # 6) 完成当前工作项（记录动作/意见）
    work_item.status = WorkItemStatus.DONE
    work_item.action = action or 'submit'
    work_item.comment = comment or ''
    work_item.owner = user
    work_item.save(update_fields=['status', 'action', 'comment', 'owner', 'updated_at'])

    ActionLog.objects.create(
        instance=ins, node=node, user=user,
        action=work_item.action, payload={'comment': work_item.comment}
    )

    # 7) 结束或流转
    if next_node.type == 'end':
        ins.status = InstanceStatus.COMPLETED
        ins.current_node = None
        ins.form_data = merged
        ins.save(update_fields=['status', 'current_node', 'form_data', 'updated_at'])
        ActionLog.objects.create(instance=ins, node=next_node, user=user, action='complete', payload={})
        return ins

    # 正常流转到下一节点：更新实例、创建新的待办
    ins.current_node = next_node
    ins.form_data = merged
    ins.save(update_fields=['current_node', 'form_data', 'updated_at'])

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