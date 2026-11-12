"""轻量级 JSON Schema 断言（无第三方依赖）。

只实现接口测试常用的子集：type / required / properties / items / enum / pattern /
minLength / minimum / maximum / additionalProperties。足够做响应契约回归，
又不必为测试环境额外安装 jsonschema。
"""
import re

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _type_ok(value, expected):
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[expected])


def validate_schema(data, schema, path="$"):
    """返回错误列表；空列表表示通过。"""
    errors = []
    expected_type = schema.get("type")
    if expected_type:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_type_ok(data, t) for t in types):
            return [f"{path}: 类型期望 {expected_type}，实际 {type(data).__name__}（值={data!r}）"]

    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: 期望枚举 {schema['enum']}，实际 {data!r}")

    if isinstance(data, str):
        if "pattern" in schema and not re.search(schema["pattern"], data):
            errors.append(f"{path}: 不匹配正则 {schema['pattern']}，实际 {data!r}")
        if "minLength" in schema and len(data) < schema["minLength"]:
            errors.append(f"{path}: 长度应 >= {schema['minLength']}，实际 {len(data)}")

    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{path}: 应 >= {schema['minimum']}，实际 {data}")
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(f"{path}: 应 <= {schema['maximum']}，实际 {data}")

    if isinstance(data, dict):
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"{path}: 缺少必填字段 {key}")
        properties = schema.get("properties", {})
        for key, sub in properties.items():
            if key in data:
                errors.extend(validate_schema(data[key], sub, f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            extra = set(data) - set(properties)
            for key in sorted(extra):
                errors.append(f"{path}: 出现未定义字段 {key}")

    if isinstance(data, list) and "items" in schema:
        for index, item in enumerate(data):
            errors.extend(validate_schema(item, schema["items"], f"{path}[{index}]"))

    return errors


def assert_schema(data, schema, path="$"):
    errors = validate_schema(data, schema, path)
    assert not errors, "响应结构不符合契约：\n" + "\n".join(errors)
