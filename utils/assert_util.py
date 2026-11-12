"""通用断言工具：HTTP 状态、业务状态码、页面/图片、服务端错误、订单号格式。"""
import re

import pytest

from utils.contract_util import assert_schema


# --------------------------------------------------------------------- 基础
def response_json(resp, *, hint=""):
    try:
        return resp.json()
    except ValueError:
        pytest.fail(
            f"响应不是合法 JSON{('：' + hint) if hint else ''}，"
            f"HTTP={resp.status_code}，body={resp.text[:500]}"
        )


def assert_http_status(resp, expected=200):
    actual = resp.status_code
    assert actual == expected, (
        f"HTTP 状态码期望 {expected}，实际 {actual}，响应：{resp.text[:500]}"
    )


def assert_status_in(resp, allowed):
    allowed = set(allowed if isinstance(allowed, (list, tuple, set)) else [allowed])
    assert resp.status_code in allowed, (
        f"HTTP 状态码期望属于 {sorted(allowed)}，实际 {resp.status_code}，响应：{resp.text[:500]}"
    )


def assert_business(resp, expected=1, *, msg_contains=None, msg_exact=None, hint=""):
    """断言 TPshop 三段式响应中的 status（可选断言 msg）。"""
    body = response_json(resp, hint=hint)
    actual = body.get("status")
    if isinstance(expected, (list, tuple, set)):
        ok = actual in expected
        expected_text = f"属于 {sorted(expected)}"
    else:
        ok = actual == expected
        expected_text = str(expected)
    assert ok, f"status 期望{expected_text}，实际 {actual}，服务端提示：{body.get('msg')}"
    if msg_exact is not None:
        assert body.get("msg") == msg_exact, (
            f"msg 期望 {msg_exact!r}，实际 {body.get('msg')!r}"
        )
    if msg_contains is not None:
        assert msg_contains in (body.get("msg") or ""), (
            f"msg 应包含 {msg_contains!r}，实际 {body.get('msg')!r}"
        )
    return body


def assert_no_server_error(resp):
    """不允许 5xx / ThinkPHP 异常页 / SQL 报错 / 代码堆栈。"""
    assert resp.status_code < 500, (
        f"接口返回 {resp.status_code}（应为业务错误而非服务端异常），响应：{resp.text[:600]}"
    )
    signatures = (
        "System Error",
        "SQLSTATE",
        "Fatal error",
        "Parse error",
        "Undefined index",
        "Undefined offset",
        "Call to a member function",
        "PHP Stack trace",
        "think\\exception",
    )
    text = resp.text or ""
    for signature in signatures:
        assert signature not in text, f"响应泄露服务端异常信息（{signature}）：{text[:600]}"


def assert_order_sn(value):
    assert isinstance(value, str) and re.fullmatch(r"\d{14,20}", value), (
        f"订单号格式不符合预期（14~20 位数字）：{value!r}"
    )


# --------------------------------------------------------------------- 页面
def assert_html(resp, *, contains=(), not_contains=()):
    assert_http_status(resp)
    content_type = (resp.headers.get("Content-Type") or "").lower()
    assert "html" in content_type, f"Content-Type 期望 HTML，实际 {content_type}"
    assert resp.text.strip(), "响应 HTML 为空"
    for text in contains:
        assert text in resp.text, f"页面应包含 {text!r}，实际前 500 字：{resp.text[:500]}"
    for text in not_contains:
        assert text not in resp.text, f"页面不应包含 {text!r}"


def assert_image(resp):
    assert_http_status(resp)
    content_type = (resp.headers.get("Content-Type") or "").lower()
    assert "image" in content_type, f"Content-Type 期望图片，实际 {content_type}"
    assert len(resp.content) > 100, f"图片响应体过小：{len(resp.content)} bytes"
    assert resp.content[:4] in (b"\x89PNG", b"GIF8", b"\xff\xd8\xff"), "响应体不是有效图片数据"


def assert_text_contains(resp, *needles):
    for needle in needles:
        assert needle in resp.text, f"响应应包含 {needle!r}，实际前 500 字：{resp.text[:500]}"


def assert_text_not_contains(resp, *needles):
    for needle in needles:
        assert needle not in resp.text, f"响应不应包含 {needle!r}"


# --------------------------------------------------------------------- 契约
def assert_contract(resp, schema):
    body = response_json(resp, hint="契约校验")
    assert_schema(body, schema)
    return body


def assert_contract_no_fields(resp, fields):
    """安全契约：响应中不得出现敏感字段（如 password/paypwd 哈希）。"""
    body = response_json(resp, hint="敏感字段校验")
    leaked = [field for field in fields if field in body.get("result", {})]
    assert not leaked, f"响应泄露敏感字段：{leaked}"
