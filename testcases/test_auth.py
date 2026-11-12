"""注册登录接口用例（对应 Excel AUTH-001 ~ AUTH-036）。

设计说明：
- 参数、预期业务码/提示、缺陷标记统一放在 `data/auth.yaml`；
- 每个反向用例使用独立会话，避免“注册成功后会话变成登录态”导致后续请求被重定向；
- 验证码一次性，每次注册/登录前都重新 GET；
- 已确认缺陷在 YAML 中配置 `bug` 字段，自动转成 xfail，修复后 XPASS。
"""
import allure
import pytest

from api.client import ApiClient
from utils.assert_util import (
    assert_business,
    assert_contract,
    assert_contract_no_fields,
    assert_image,
    assert_no_server_error,
)
from utils.contracts import LOGIN_SUCCESS, REGISTER_SUCCESS
from utils.crypto_util import encrypt_password
from utils.data_util import load_data, param_cases
from utils.flow_util import new_phone


FEATURE = "注册登录"
AUTH = load_data("auth")
COMMON = load_data("common")


def title(case_id, text):
    allure.dynamic.title(f"{case_id} {text}")


def register(client, *, username=None, password=COMMON["password"], **kwargs):
    client.user.get_register_verify()
    return client.user.register(
        username if username is not None else new_phone(), password, **kwargs
    )


@allure.feature(FEATURE)
class TestAuth:
    # ------------------------------------------------------------ 验证码
    def test_AUTH_001_register_verify(self, anon):
        title("AUTH-001", "获取注册图片验证码成功")
        assert_image(anon.user.get_register_verify())

    @pytest.mark.xfail(
        reason="新缺陷：验证码接口不校验 type 路径参数，任意 type 都返回图片",
        strict=False,
    )
    def test_AUTH_002_verify_type_invalid(self, anon):
        title("AUTH-002", "验证码接口 type 路径参数非法")
        resp = anon.user.get("/index.php/Home/User/verify/type/xxx.html")
        assert_no_server_error(resp)
        content_type = (resp.headers.get("Content-Type") or "").lower()
        assert resp.status_code == 404 or "image" not in content_type, (
            f"非法 type 仍返回图片验证码：HTTP={resp.status_code}, CT={content_type}"
        )

    def test_AUTH_003_refresh_verify_10_times(self, anon):
        title("AUTH-003", "连续刷新验证码 10 次")
        bodies = []
        for _ in range(10):
            resp = anon.user.get_register_verify()
            assert_image(resp)
            bodies.append(resp.content)
        assert len(set(bodies)) > 1, "连续 10 次验证码图片完全相同，疑似静态图"

    def test_AUTH_004_verify_without_cookie(self, anon):
        title("AUTH-004", "验证码接口未携带会话")
        resp = anon.user.get_login_verify()
        assert_no_server_error(resp)
        content_type = (resp.headers.get("Content-Type") or "").lower()
        assert "image" in content_type or "json" in content_type, (
            f"无 Cookie 请求返回异常：HTTP={resp.status_code}, CT={content_type}"
        )

    # ---------------------------------------------------------------- 注册
    def test_AUTH_005_register_success(self, anon):
        title("AUTH-005", "注册成功")
        phone = new_phone()
        resp = register(anon, username=phone)
        assert_contract(resp, REGISTER_SUCCESS)
        assert resp.json()["result"]["mobile"] == phone, "注册返回手机号与提交不一致"

    def test_AUTH_006_register_duplicate(self):
        title("AUTH-006", "手机号已注册")
        phone = new_phone()
        first = ApiClient()
        assert register(first, username=phone).json().get("status") == 1

        second = ApiClient()
        resp = register(second, username=phone)
        assert_business(resp, expected=-1, msg_exact="该手机号已注册")

    @pytest.mark.parametrize("case", param_cases(AUTH["register_negative"]))
    def test_AUTH_007_008_register_negative(self, anon, case):
        title(case["id"], case["title"])
        resp = register(anon, **case["request"])
        assert_business(
            resp, expected=case["expect_status"], msg_exact=case["expect_msg"]
        )

    @pytest.mark.parametrize("case", param_cases(AUTH["auth_code"]))
    def test_AUTH_009_010_auth_code(self, anon, case):
        title(case["id"], case["title"])
        resp = register(anon, **case["request"])
        assert_business(resp, expected=case["expect_status"])

    @pytest.mark.parametrize("case", param_cases([AUTH["scene_missing"]]))
    def test_AUTH_011_scene_missing(self, anon, case):
        title(case["id"], case["title"])
        resp = register(anon, **case["request"])
        assert_business(resp, expected=case["expect_status"])

    @pytest.mark.parametrize("case", param_cases(AUTH["scene_invalid"]))
    def test_AUTH_012_scene_invalid(self, anon, case):
        title("AUTH-012", f"scene 取值非法（{case['value']}）")
        resp = register(anon, scene=case["value"])
        assert_no_server_error(resp)
        assert_business(resp, expected=[1, -1])

    def test_AUTH_013_username_missing(self, anon):
        title("AUTH-013", "username 缺失")
        resp = register(anon, omit=("username",))
        assert_business(
            resp, expected=-1, msg_exact=AUTH["username_format_msg"]
        )

    @pytest.mark.parametrize("case", param_cases(AUTH["username_invalid"]))
    def test_AUTH_014_username_invalid(self, anon, case):
        title("AUTH-014", f"username 格式非法（{case['value']}）")
        resp = register(anon, username=case["value"])
        assert_business(
            resp, expected=-1, msg_exact=AUTH["username_format_msg"]
        )

    @pytest.mark.parametrize("case", param_cases(AUTH["required_params"]))
    def test_AUTH_015_017_required_params(self, anon, case):
        title(case["id"], f"必填参数缺失（{case['field']}）")
        resp = register(anon, omit=(case["field"],))
        assert_business(resp, expected=-1, msg_exact=case["expect_msg"])

    @pytest.mark.parametrize("case", param_cases(AUTH["password_lengths"]))
    def test_AUTH_018_password_length(self, anon, case):
        title("AUTH-018", f"密码长度边界（{case['length']} 位）")
        password = ("Abc@1234567890xyz" * 2)[: case["length"]]
        resp = register(anon, password=password)
        assert_no_server_error(resp)
        assert_business(resp, expected=1 if case["should_succeed"] else -1)

    def test_AUTH_019_invite_optional(self, anon):
        title("AUTH-019", "invite 选填不传")
        resp = register(anon, omit=("invite",))
        assert_business(resp, expected=1)

    def test_AUTH_021_without_content_type(self, anon):
        title("AUTH-021", "请求头 Content-Type 缺失")
        anon.user.get_register_verify()
        payload = (
            f"auth_code=TPSHOP&scene=1&username={new_phone()}&verify_code=8888"
            f"&password={encrypt_password(COMMON['password'])}"
            f"&password2={encrypt_password(COMMON['password'])}&invite="
        )
        resp = anon.user.post(
            "/Home/User/reg.html", data=payload, headers={"Content-Type": None}
        )
        assert_no_server_error(resp)
        assert_business(resp, expected=[1, -1])

    @pytest.mark.xfail(
        reason="新缺陷：失效 Cookie 注册返回 500 System Error", strict=False
    )
    def test_AUTH_022_register_with_invalid_session(self):
        title("AUTH-022", "会话失效时注册")
        client = ApiClient()
        client.session.cookies.set(
            "PHPSESSID", AUTH["security"]["invalid_session_cookie"]
        )
        resp = register(client, username=new_phone())
        assert_no_server_error(resp)
        assert_business(resp, expected=-1)

    def test_AUTH_023_duplicate_submit(self):
        title("AUTH-023", "注册接口重复提交（5 次）")
        phone = new_phone()
        statuses = []
        for _ in range(AUTH["security"]["duplicate_attempts"]):
            client = ApiClient()
            resp = register(client, username=phone)
            assert_no_server_error(resp)
            statuses.append(resp.json().get("status"))
        assert statuses[0] == 1, f"首次注册应成功，实际 {statuses}"
        assert all(status != 1 for status in statuses[1:]), (
            f"重复注册出现多次成功：{statuses}"
        )

    def test_AUTH_024_register_sql_injection(self, anon):
        title("AUTH-024", "注册参数注入与脚本")
        payload = AUTH["security"]["register_sql_injection"]
        resp = register(anon, username=payload["username"], invite=payload["invite"])
        assert_no_server_error(resp)
        assert_business(resp, expected=-1)
        assert "SQLSTATE" not in resp.text and "root@" not in resp.text

    def test_AUTH_025_captcha_one_time(self):
        title("AUTH-025", "验证码一次性校验")
        client = ApiClient()
        client.user.get_register_verify()
        first = client.user.register(new_phone(), COMMON["password"], password2="Different1")
        assert_business(first, expected=-1, msg_exact="两次密码不一致")
        second = client.user.register(new_phone(), COMMON["password"])
        assert_business(second, expected=-1, msg_exact="图像验证码错误")

    # ---------------------------------------------------------------- 登录
    def test_AUTH_026_login_verify(self, anon):
        title("AUTH-026", "获取登录图片验证码")
        assert_image(anon.user.get_login_verify())

    def test_AUTH_028_login_success(self, anon):
        title("AUTH-028", "登录成功")
        anon.user.get_login_verify()
        resp = anon.user.login()
        assert_contract(resp, LOGIN_SUCCESS)

    @pytest.mark.xfail(
        reason="BUG-10：登录响应返回 password / paypwd 哈希", strict=False
    )
    def test_SEC_login_no_password_leak(self, anon):
        title("SEC", "登录响应不得返回密码哈希")
        anon.user.get_login_verify()
        resp = anon.user.login()
        assert_contract_no_fields(resp, ["password", "paypwd"])

    @pytest.mark.parametrize("case", param_cases(AUTH["login_negative"]))
    def test_AUTH_029_033_login_negative(self, anon, case):
        title(case["id"], case["title"])
        anon.user.get_login_verify()
        resp = anon.user.login(**case["request"])
        assert_business(
            resp, expected=case["expect_status"], msg_exact=case["expect_msg"]
        )

    @pytest.mark.parametrize("verify_code", AUTH["verify_code_types"])
    def test_AUTH_034_verify_code_type(self, anon, verify_code):
        title("AUTH-034", f"verify_code 类型与边界（{verify_code!r}）")
        anon.user.get_login_verify()
        resp = anon.user.login(verify_code=verify_code)
        assert_no_server_error(resp)
        assert_business(resp, expected=0, msg_exact="验证码错误")

    @pytest.mark.parametrize("t", AUTH["t_params"])
    def test_AUTH_035_t_param(self, anon, t):
        title("AUTH-035", f"t 参数缺失或非法（{t!r}）")
        anon.user.get_login_verify()
        resp = anon.user.login(t=t)
        assert_business(resp, expected=1)

    def test_AUTH_036_login_sql_injection(self, anon):
        title("AUTH-036", "登录接口 SQL 注入")
        anon.user.get_login_verify()
        payload = AUTH["security"]["login_sql_injection"]
        resp = anon.user.login(username=payload["username"], password=payload["password"])
        assert_no_server_error(resp)
        assert_business(resp, expected=-1)
        assert "user_id" not in (resp.json().get("result") or {})
