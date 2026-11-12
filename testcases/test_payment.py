"""支付验证接口用例（对应 Excel PAY-001 ~ PAY-012）。

TPshop 货到付款是伪支付：getCode 只写 pay_code，pay_status 仍为 0，
真正的付款动作在后台“订单付款”。因此本模块只断言支付入口/页面行为，
支付成功状态由后台订单用例覆盖。输入与预期提示统一放在 `data/payment.yaml`。
"""
import allure
import pytest

from utils.assert_util import (
    assert_html,
    assert_no_server_error,
    assert_text_contains,
)
from utils.data_util import load_data, param_cases


FEATURE = "支付验证"
PAY = load_data("payment")


def title(case_id, text):
    allure.dynamic.title(f"{case_id} {text}")


@allure.feature(FEATURE)
class TestPayment:
    def test_PAY_001_pay_cod_success(self, order):
        title("PAY-001", "货到付款支付成功（伪支付入口）")
        resp = order.account.client.payment.pay_cod(order.id)
        assert_html(resp, contains=("支付", order.id))
        assert "System Error" not in resp.text

    def test_PAY_002_pay_radio_missing(self, order):
        case = PAY["pay_radio_missing"]
        title("PAY-002", "pay_radio 缺失")
        resp = order.account.client.payment.pay_cod(order.id, **case["request"])
        assert_no_server_error(resp)
        assert_text_contains(resp, case["needle"])
        assert "付款金额" not in resp.text, "pay_radio 缺失仍进入支付页"

    @pytest.mark.parametrize(
        "case", param_cases([PAY["pay_radio_invalid"]])
    )
    def test_PAY_003_pay_radio_invalid(self, order, case):
        title("PAY-003", "pay_radio 取值非法（weixin）")
        resp = order.account.client.payment.pay_cod(
            order.id, pay_radio=case["value"]
        )
        assert_no_server_error(resp)
        assert_text_contains(resp, "不支持的支付方式")

    @pytest.mark.parametrize("case", param_cases(PAY["order_id_invalid"]))
    def test_PAY_004_005_order_id_invalid(self, order, case):
        title(case["id"].rsplit("-", 1)[0], "order_id 缺失或不存在")
        resp = order.account.client.payment.pay_cod(**case["request"])
        assert_no_server_error(resp)
        assert_text_contains(resp, case["needle"])
        assert "付款金额" not in resp.text

    @pytest.mark.xfail(
        reason="BUG-05：水平越权，可为他人订单发起支付", strict=False
    )
    def test_PAY_006_pay_other_user_order(self, order, account):
        title("PAY-006", "为他人订单支付（越权）")
        resp = account.client.payment.pay_cod(order.id)
        assert_no_server_error(resp)
        assert order.id not in resp.text and "付款金额" not in resp.text, "他人订单被成功发起支付"

    def test_PAY_007_repeat_pay(self, order):
        title("PAY-007", "已支付订单重复支付")
        first = order.account.client.payment.pay_cod(order.id)
        second = order.account.client.payment.pay_cod(order.id)
        for resp in (first, second):
            assert_no_server_error(resp)
            assert "System Error" not in resp.text
        assert_html(second, contains=("支付",))

    def test_PAY_008_pay_without_login(self, order, anon):
        title("PAY-008", "未登录发起支付")
        resp = anon.payment.pay_cod(order.id)
        assert_no_server_error(resp)
        assert "付款金额" not in resp.text, "未登录仍渲染出支付金额"

    @pytest.mark.parametrize("master_order_sn", PAY["master_order_sn"])
    def test_PAY_009_master_order_sn(self, order, master_order_sn):
        title("PAY-009", f"master_order_sn 选填校验（{master_order_sn!r}）")
        resp = order.account.client.payment.pay_cod(
            order.id, master_order_sn=master_order_sn
        )
        assert_no_server_error(resp)
        assert_html(resp, contains=("支付", order.id))

    def test_PAY_010_payment_status(self, order):
        title("PAY-010", "查看支付状态")
        resp = order.account.client.payment.payment_status(order.sn)
        assert_html(resp, contains=(order.sn,))

    def test_PAY_011_payment_status_not_exist(self, order):
        title("PAY-011", "订单号不存在时查看支付状态")
        resp = order.account.client.payment.payment_status(PAY["invalid_order_sn"])
        assert_no_server_error(resp)
        assert "System Error" not in resp.text

    @pytest.mark.xfail(
        reason="BUG-17：支付状态页跨用户回显他人订单号", strict=False
    )
    def test_PAY_012_payment_status_other_user(self, order, account):
        title("PAY-012", "查看他人支付状态（越权）")
        resp = account.client.payment.payment_status(order.sn)
        assert_no_server_error(resp)
        assert order.sn not in resp.text, "支付状态页泄露了他人订单号"

