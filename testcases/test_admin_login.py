"""后台登录接口用例（对应 Excel ADMLOGIN-001 ~ ADMLOGIN-011）。"""
import allure
import pytest

from utils.assert_util import (
    assert_business,
    assert_contract,
    assert_image,
    assert_no_server_error,
)
from utils.contracts import ADMIN_LOGIN_SUCCESS


FEATURE = "后台登录"


def title(case_id, text):
    allure.dynamic.title(f"{case_id} {text}")


@allure.feature(FEATURE)
class TestAdminLogin:
    def test_ADMLOGIN_001_verify(self, anon):
        title("ADMLOGIN-001", "获取后台登录验证码")
        assert_image(anon.admin.get_verify())

    def test_ADMLOGIN_002_login_success(self, anon):
        title("ADMLOGIN-002", "后台登录成功")
        anon.admin.get_verify()
        assert_contract(anon.admin.login(), ADMIN_LOGIN_SUCCESS)

    @pytest.mark.parametrize(
        "kwargs,case_id,expected_msg",
        [
            pytest.param(dict(password="wrong_pwd"), "ADMLOGIN-003", None, id="ADMLOGIN-003"),
            pytest.param(dict(verify_code="0000"), "ADMLOGIN-004", "验证码错误", id="ADMLOGIN-004"),
            pytest.param(dict(username="", password=""), "ADMLOGIN-005", "请填写账号密码", id="ADMLOGIN-005"),
        ],
    )
    def test_ADMLOGIN_003_005_login_negative(self, anon, kwargs, case_id, expected_msg):
        title(case_id, "账号密码/验证码错误或为空")
        anon.admin.get_verify()
        resp = anon.admin.login(**kwargs)
        assert_no_server_error(resp)
        assert_business(resp, expected=0, msg_exact=expected_msg)

    @pytest.mark.parametrize(
        "omit",
        [
            pytest.param(("username",), id="ADMLOGIN-006-缺username"),
            pytest.param(("password",), id="ADMLOGIN-007-缺password"),
        ],
    )
    def test_ADMLOGIN_006_007_required(self, anon, omit):
        title("ADMLOGIN-006/007", f"必填参数缺失（{omit[0]}）")
        anon.admin.get_verify()
        data = {"username": "admin", "password": "123456", "vertify": "8888"}
        data.pop(omit[0])
        resp = anon.admin.post("/index.php?m=Admin&c=Admin&a=login", data=data)
        assert_business(resp, expected=0, msg_exact="请填写账号密码")

    @pytest.mark.parametrize("vertify", ["abcd", "", "123456789"])
    def test_ADMLOGIN_008_vertify_type(self, anon, vertify):
        title("ADMLOGIN-008", f"vertify 类型与边界（{vertify!r}）")
        anon.admin.get_verify()
        resp = anon.admin.login(verify_code=vertify)
        assert_no_server_error(resp)
        assert_business(resp, expected=0, msg_exact="验证码错误")

    def test_ADMLOGIN_010_sql_injection(self, anon):
        title("ADMLOGIN-010", "后台登录 SQL 注入")
        anon.admin.get_verify()
        resp = anon.admin.login(username="admin' or '1'='1", password="x")
        assert_no_server_error(resp)
        assert_business(resp, expected=0)
        assert "url" not in resp.json() or "Index/index" not in (
            resp.json().get("url") or ""
        )

    def test_ADMLOGIN_011_admin_page_without_login(self, anon):
        title("ADMLOGIN-011", "未登录直接访问后台页面")
        resp = anon.admin.get(
            "/index.php/Admin/Index/index", allow_redirects=True
        )
        assert_no_server_error(resp)
        assert "Index/index" not in resp.url, f"未登录未被拦截，最终 URL={resp.url}"
        assert "登录" in resp.text or "login" in resp.url.lower(), (
            "未登录访问后台页面既未跳转登录也未返回未授权"
        )
