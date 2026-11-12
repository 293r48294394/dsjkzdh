"""后台订单接口用例（对应 Excel ADMORDER-001 ~ ADMORDER-018）。

注意 TPshop 状态机顺序：后台付款会把 order_status 重置为 0，
因此必须先“付款”再“确认”，最后“发货”。
"""
import allure
import pytest

from utils.assert_util import (
    assert_business,
    assert_contract,
    assert_html,
    assert_no_server_error,
    assert_text_contains,
)
from utils.contracts import ADMIN_ACTION_SUCCESS


FEATURE = "后台确认订单"


def title(case_id, text):
    allure.dynamic.title(f"{case_id} {text}")


def rec_id_of(admin, order):
    page = admin.admin.delivery_info(order.id)
    ids = admin.admin.extract_rec_id(page)
    assert ids, f"发货页未解析到 goods[]：{page.text[:300]}"
    return ids[0]


@allure.feature(FEATURE)
class TestAdminOrder:
    # ------------------------------------------------------------ 确认订单
    def test_ADMORDER_001_confirm_success(self, admin, paid_order):
        title("ADMORDER-001", "后台确认订单成功")
        assert_contract(
            admin.admin.confirm(paid_order.id, note="测试确认"), ADMIN_ACTION_SUCCESS
        )

    def test_ADMORDER_002_confirm_order_id_missing(self, admin):
        title("ADMORDER-002", "order_id 缺失")
        resp = admin.admin.confirm()
        assert_business(resp, expected=0, msg_exact="参数错误")

    @pytest.mark.xfail(
        reason="BUG-09：order_id 不存在时返回 500 SQL 错误", strict=False
    )
    def test_ADMORDER_003_confirm_order_not_exist(self, admin):
        title("ADMORDER-003", "order_id 不存在")
        resp = admin.admin.confirm("999999")
        assert_no_server_error(resp)
        assert_business(resp, expected=0)

    @pytest.mark.parametrize(
        "note",
        [
            pytest.param("", id="ADMORDER-004-note缺省"),
            pytest.param("测" * 200, id="ADMORDER-004-note超长"),
        ],
    )
    def test_ADMORDER_004_note(self, admin, paid_order, note):
        title("ADMORDER-004", f"note 选填与长度边界（{len(note)} 字）")
        resp = admin.admin.confirm(paid_order.id, note=note)
        assert_no_server_error(resp)
        assert_business(resp, expected=1)

    def test_ADMORDER_005_confirm_without_login(self, anon, paid_order):
        title("ADMORDER-005", "未登录或无权限确认订单")
        resp = anon.admin.confirm(paid_order.id)
        assert_no_server_error(resp)
        assert resp.status_code in (200, 302)
        assert "操作成功" not in resp.text

    # ---------------------------------------------------------------- 付款
    def test_ADMORDER_006_pay_success(self, admin, order):
        title("ADMORDER-006", "后台确认付款成功")
        assert_contract(
            admin.admin.pay(order.id, note="货到付款收款"), ADMIN_ACTION_SUCCESS
        )

    def test_ADMORDER_007_pay_order_id_missing(self, admin):
        title("ADMORDER-007", "后台付款 order_id 缺失")
        resp = admin.admin.pay()
        assert_business(resp, expected=0, msg_exact="参数错误")

    @pytest.mark.xfail(
        reason="BUG-16：重复后台付款返回“操作成功”但未产生任何变更", strict=False
    )
    def test_ADMORDER_008_repeat_pay(self, admin, paid_order):
        title("ADMORDER-008", "重复确认付款")
        resp = admin.admin.pay(paid_order.id)
        assert_business(resp, expected=0)

    @pytest.mark.xfail(
        reason="BUG-03：已取消订单可以再次确认付款并复活", strict=False
    )
    def test_ADMORDER_009_pay_cancelled_order(self, admin, order):
        title("ADMORDER-009", "对已取消订单确认付款")
        cancel = order.account.client.order.cancel(order.id)
        assert_business(cancel, expected=1)
        resp = admin.admin.pay(order.id)
        assert_business(resp, expected=0)

    # ---------------------------------------------------------------- 发货
    def test_ADMORDER_010_delivery_info(self, admin, confirmed_order):
        title("ADMORDER-010", "打开发货页面")
        page = admin.admin.delivery_info(confirmed_order.id)
        assert_html(page)
        assert admin.admin.extract_rec_id(page), "发货页未解析到 goods[]"
        assert "shipping_name" in page.text and "invoice_no" in page.text

    @pytest.mark.xfail(
        reason="BUG-09：不存在的订单打开发货页返回 500", strict=False
    )
    def test_ADMORDER_011_delivery_info_not_exist(self, admin):
        title("ADMORDER-011", "发货页面订单 ID 不存在")
        resp = admin.admin.delivery_info("999999")
        assert_no_server_error(resp)

    def test_ADMORDER_012_delivery_info_without_login(self, anon, confirmed_order):
        title("ADMORDER-012", "未登录访问发货页面")
        resp = anon.admin.delivery_info(confirmed_order.id)
        assert_no_server_error(resp)
        assert "goods[]" not in resp.text, "未登录仍能获取发货表单"
        assert "收货人" not in resp.text

    def test_ADMORDER_013_delivery_success(self, admin, confirmed_order):
        title("ADMORDER-013", "确认发货成功")
        rec_id = rec_id_of(admin, confirmed_order)
        resp = admin.admin.delivery(confirmed_order.id, rec_id, invoice_no="123456789")
        assert_no_server_error(resp)
        assert_text_contains(resp, "操作成功")

    @pytest.mark.xfail(
        reason="新缺陷：未校验 shipping_name / shipping_code 必填", strict=False
    )
    @pytest.mark.parametrize(
        "omit",
        [
            pytest.param(("shipping_name",), id="ADMORDER-014-缺快递公司名"),
            pytest.param(("shipping_code",), id="ADMORDER-014-缺快递公司编码"),
        ],
    )
    def test_ADMORDER_014_shipping_required(self, admin, confirmed_order, omit):
        title("ADMORDER-014", f"快递公司参数缺失（{omit[0]}）")
        rec_id = rec_id_of(admin, confirmed_order)
        resp = admin.admin.delivery(confirmed_order.id, rec_id, omit=omit)
        assert_no_server_error(resp)
        assert "操作成功" not in resp.text

    @pytest.mark.xfail(
        reason="新缺陷：invoice_no 非数字/超长未被拒绝或截断", strict=False
    )
    @pytest.mark.parametrize(
        "invoice_no",
        [
            pytest.param("abc", id="ADMORDER-015-非数字"),
            pytest.param("9" * 20, id="ADMORDER-015-超长"),
        ],
    )
    def test_ADMORDER_015_invoice_invalid(self, admin, confirmed_order, invoice_no):
        title("ADMORDER-015", f"快递单号取值异常（{invoice_no[:8]}）")
        rec_id = rec_id_of(admin, confirmed_order)
        resp = admin.admin.delivery(confirmed_order.id, rec_id, invoice_no=invoice_no)
        assert_no_server_error(resp)
        assert "操作成功" not in resp.text

    @pytest.mark.xfail(
        reason="BUG-06/BUG-09：缺 goods[] 发货返回 500 且残留发货单", strict=False
    )
    def test_ADMORDER_016_goods_missing(self, admin, confirmed_order):
        title("ADMORDER-016", "goods 商品种类缺失")
        rec_id = rec_id_of(admin, confirmed_order)
        resp = admin.admin.delivery(confirmed_order.id, rec_id, omit=("goods[]",))
        assert_no_server_error(resp)
        assert_business(resp, expected=0)

    @pytest.mark.xfail(
        reason="BUG-02：未确认订单可以直接发货", strict=False
    )
    def test_ADMORDER_017_deliver_unconfirmed(self, admin, paid_order):
        title("ADMORDER-017", "对未确认订单发货")
        rec_id = rec_id_of(admin, paid_order)
        resp = admin.admin.delivery(paid_order.id, rec_id)
        assert "操作成功" not in resp.text

    def test_ADMORDER_018_delivery_without_login(self, anon, admin, confirmed_order):
        title("ADMORDER-018", "未登录或无权限发货")
        rec_id = rec_id_of(admin, confirmed_order)
        resp = anon.admin.delivery(confirmed_order.id, rec_id)
        assert_no_server_error(resp)
        assert "操作成功" not in resp.text
