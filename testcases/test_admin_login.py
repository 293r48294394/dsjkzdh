"""后台登录接口用例（对应 Excel ADMLOGIN-001 ~ ADMLOGIN-011）。

输入、边界值与预期提示统一放在 `data/admin_login.yaml`。
"""
import allure
import pytest

from utils.assert_util import (
    assert_business,
    assert_contract,
    assert_image,
    assert_no_server_error,
)
from utils.contracts import ADMIN_LOGIN_SUCCESS
from utils.data_util import load_data, param_cases


FEATURE = "后台登录"
ADMIN = load_data("admin_login")


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

    @pytest.mark.parametrize("case", param_cases(ADMIN["login_negative"]))
    def test_ADMLOGIN_003_005_login_negative(self, anon, case):
        title(case["id"], case["title"])
        anon.admin.get_verify()
        resp = anon.admin.login(**case["request"])
        assert_no_server_error(resp)
        assert_business(
            resp, expected=case["expect_status"], msg_exact=case["expect_msg"]
        )

    @pytest.mark.parametrize("case", param_cases(ADMIN["required"]))
    def test_ADMLOGIN_006_007_required(self, anon, case):
        title("ADMLOGIN-006/007", f"必填参数缺失（{case['field']}）")
        anon.admin.get_verify()
        data = {"username": "admin", "password": "123456", "vertify": "8888"}
        data.pop(case["field"])
        resp = anon.admin.post("/index.php?m=Admin&c=Admin&a=login", data=data)
        assert_business(resp, expected=0, msg_exact="请填写账号密码")

    @pytest.mark.parametrize("vertify", ADMIN["vertify_types"])
    def test_ADMLOGIN_008_vertify_type(self, anon, vertify):
        title("ADMLOGIN-008", f"vertify 类型与边界（{vertify!r}）")
        anon.admin.get_verify()
        resp = anon.admin.login(verify_code=vertify)
        assert_no_server_error(resp)
        assert_business(resp, expected=0, msg_exact="验证码错误")

    def test_ADMLOGIN_010_sql_injection(self, anon):
        title("ADMLOGIN-010", "后台登录 SQL 注入")
        anon.admin.get_verify()
        payload = ADMIN["sql_injection"]
        resp = anon.admin.login(
            username=payload["username"], password=payload["password"]
        )
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
