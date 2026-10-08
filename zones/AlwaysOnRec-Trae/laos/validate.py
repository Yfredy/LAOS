"""零依赖最小 JSON-schema 校验 + 路径穿越语义围栏。

堵 AIOS Tool Manager 的洞：AIOS 把 tool_params 原样传入 tool.run，
既不校验类型也不校验路径；这里在 kernel.syscall 网关内补上，且校验由内核执行。
"""
from __future__ import annotations

import re


class ValidationError(Exception):
    pass


_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def validate_args(schema: dict, args: dict) -> None:
    if not schema or schema.get("type") != "object":
        return
    props = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in args:
            raise ValidationError(f"EINVAL: missing required arg '{key}'")
    for key, val in args.items():
        spec = props.get(key)
        if spec is None:
            continue
        _check_type(key, val, spec.get("type"))
        if "enum" in spec and val not in spec["enum"]:
            raise ValidationError(f"EINVAL: '{key}'={val!r} not in {spec['enum']}")
        if spec.get("type") == "string" and "pattern" in spec:
            if not re.search(spec["pattern"], str(val)):
                raise ValidationError(f"EINVAL: '{key}'={val!r} violates pattern")
        # 语义围栏：路径类字段禁止穿越（超越纯模式匹配，覆盖 jail 之前）。
        # 沿用 laos jail 约定返回 EACCES，与既有测试/驱动层一致。
        if spec.get("type") == "string" and isinstance(val, str):
            if ".." in val or val.startswith("../") or "/.." in val:
                raise ValidationError(f"EACCES: path traversal in '{key}'")


def _check_type(key: str, val, type_: str | None) -> None:
    if type_ is None:
        return
    expect = _TYPES.get(type_)
    if expect is None:
        return
    # bool 是 int 子类，单独排除
    if type_ == "integer" and isinstance(val, bool):
        raise ValidationError(f"EINVAL: '{key}' must be integer")
    if not isinstance(val, expect):
        raise ValidationError(f"EINVAL: '{key}' must be {type_}, got {type(val).__name__}")
