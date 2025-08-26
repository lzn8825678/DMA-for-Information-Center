# flow/utils.py
from __future__ import annotations
from typing import Any, Dict, Tuple, List
import ast

ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.IfExp,
    ast.Compare, ast.Call, ast.Load, ast.Name, ast.Constant,
    ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
    ast.Gt, ast.GtE, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
)

ALLOWED_NAMES = {"True": True, "False": False, "None": None}

def safe_eval(expr: str, ctx: Dict[str, Any]) -> bool:
    """
    仅允许白名单 AST 的简单表达式；上下文仅通过 ctx（如 form、action）。
    """
    if not expr:
        return True
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"不允许的表达式节点: {type(node).__name__}")
        if isinstance(node, ast.Call):
            # 禁止函数调用（如 len()），需要的话可在此白名单函数名并自定义实现
            raise ValueError("不允许在条件中调用函数")
    code = compile(tree, "<cond>", "eval")
    env = dict(ALLOWED_NAMES)
    env.update(ctx or {})
    return bool(eval(code, {"__builtins__": {}}, env))


def merge_overrides(json_schema: Dict[str, Any], overrides: Dict[str, Any]|None) -> Dict[str, Any]:
    """
    将节点 form_overrides 合并为易用的权限集：
    返回 dict：{hidden:set, readonly:set, required:set}
    """
    o = overrides or {}
    return {
        "hidden": set(o.get("hidden") or []),
        "readonly": set(o.get("readonly") or []),
        "required": set(o.get("required") or []),
    }

def schema_required(schema: Dict[str, Any]) -> set[str]:
    req = schema.get("required") or []
    return set(req if isinstance(req, list) else [])

def schema_properties(schema: Dict[str, Any]) -> Dict[str, Any]:
    props = schema.get("properties") or {}
    return props if isinstance(props, dict) else {}

def normalize_types(props: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """
    按 JSON Schema 的 type 尝试做基本类型转换。
    """
    out = dict(data)
    for k, meta in props.items():
        t = meta.get("type")
        if k not in out:
            continue
        v = out[k]
        if v is None or v == "":
            continue
        try:
            if t == "integer":
                out[k] = int(v)
            elif t == "number":
                out[k] = float(v)
            elif t == "boolean":
                if isinstance(v, bool): pass
                elif str(v).lower() in ("true", "1", "yes", "on"): out[k] = True
                elif str(v).lower() in ("false", "0", "no", "off"): out[k] = False
            # string/others 不处理
        except Exception:
            # 类型转换失败时，保留原值，交由业务判断
            pass
    return out

def validate_form(
    schema: Dict[str, Any],
    overrides: Dict[str, set],
    data: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    校验：必填（schema.required ∪ overrides.required），隐藏字段不允许提交，readonly 字段不可被修改。
    注意：readonly 的“不可修改”校验由服务层负责（对比旧值）。
    """
    props = schema_properties(schema)
    req = schema_required(schema) | overrides["required"]

    errors: List[str] = []

    # 隐藏字段：如果传上来了，提示错误（前端应不渲染；后端兜底）
    for k in overrides["hidden"]:
        if k in data and data[k] not in ("", None):
            errors.append(f"字段“{k}”不可提交")

    # 必填字段
    for k in req:
        if k not in data or data[k] in ("", None):
            errors.append(f"字段“{k}”为必填")

    # 基于 props 的枚举校验（如果有 enum）
    for k, meta in props.items():
        if k in data and "enum" in meta and isinstance(meta["enum"], list):
            if data[k] not in ("", None) and data[k] not in meta["enum"]:
                errors.append(f"字段“{k}”必须是枚举值之一：{meta['enum']}")

    return (len(errors) == 0, errors)
