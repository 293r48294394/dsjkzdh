"""YAML 测试数据加载与参数化工具。

分层约定：
- `config/config.yaml`：环境配置（地址、账号、商品、验证码、清理前缀）；
- `data/*.yaml`：测试数据（输入、边界、预期业务码/提示、缺陷标记）；
- 测试代码只负责编排步骤与断言，不在用例里散落大段参数。
"""
from functools import lru_cache
from pathlib import Path

import pytest
import yaml


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


@lru_cache(maxsize=None)
def load_data(name):
    """读取 data/<name>.yaml，进程内缓存。"""
    path = DATA_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"未找到测试数据文件：{path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_data(name, key, default=None):
    """按点号读取嵌套数据，如 get_data("cart", "submit.address_missing")。"""
    value = load_data(name)
    for part in key.split("."):
        if not isinstance(value, dict):
            return default
        value = value.get(part)
        if value is None:
            return default
    return value


def param_cases(cases):
    """把 YAML 用例列表转换为 pytest.param 列表。

    用例字段：
    - id：必填，pytest 用例 ID（与 Excel 编号一致）；
    - title：Allure 标题；
    - bug：可选，填写缺陷说明后自动标记 xfail，修复后 XPASS。
    """
    params = []
    for case in cases:
        bug = case.get("bug")
        marks = pytest.mark.xfail(reason=bug, strict=False) if bug else ()
        params.append(pytest.param(case, id=case["id"], marks=marks))
    return params


def expand_text(spec):
    """展开 YAML 中的长文本定义，如 {char: "测", times: 2000}。"""
    if not spec:
        return ""
    return str(spec["char"]) * int(spec["times"])
