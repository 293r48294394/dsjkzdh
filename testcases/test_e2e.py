"""全链路联调用例（对应 Excel E2E-001 ~ E2E-035 中可自动化的场景）。

不可自动化项：
- E2E-006 多商品：环境只有 goods_id=1 可稳定下单，3 件商品数据不齐；
- E2E-015/018/029/030/031/034/036：依赖会话失效、库存/金额口径、前后台状态文案或 DB 核对，列为半自动；
- E2E-025/028：并发/超卖属于压测工具范畴，不放在接口回归里。
"""
import allure
import pytest

from utils.assert_util import (
    assert_business,
    assert_html,
    assert_no_server_error,
    assert_order_sn,
    assert_text_contains,
)
from utils.data_util import load_data
from utils.flow_util import place_order


FEATURE = "全链路联调"
E2E = load_data("e2e")
COMMON = load_data("common")


def title(case_id, text):
    allure.dynamic.title(f"{case_id} {text}")


@allure.feature(FEATURE)
class TestE2E:
    # ------------------------------------------------------------ 完整链路
    @pytest.mark.e2e
    @pytest.mark.smoke
    def test_E2E_001_new_user_full_flow(self, account_factory, admin):
        title("E2E-001", "新用户全链路：注册→登录→加购→下单→支付→履约→收货→评价")
        account = account_factory(with_address=True)
        client = account.client

        with allure.step("注册并登录新用户"):
            assert account.user_id, "注册未返回 user_id"
            assert account.address_id, "新用户地址创建失败"

        with allure.step("加购并提交订单"):
            placed = place_order(account)
            order_sn, order_id = placed.sn, placed.id
            assert_order_sn(order_sn)

        with allure.step("按订单号获取订单 id"):
            assert client.cart.get_order_id(order_sn) == order_id
            page = client.cart.get_order_info(order_sn)
            assert_html(page, contains=(order_sn, f'value="{order_id}"'))

        with allure.step("发起货到付款"):
            assert_html(client.payment.pay_cod(order_id), contains=("支付",))
            assert_html(client.payment.payment_status(order_sn), contains=(order_sn,))

        with allure.step("后台付款并确认订单"):
            assert_business(admin.admin.pay(order_id), expected=1)
            assert_business(admin.admin.confirm(order_id), expected=1)

        with allure.step("后台发货"):
            page = admin.admin.delivery_info(order_id)
            rec_ids = admin.admin.extract_rec_id(page)
            assert rec_ids, "发货页未解析到 goods[]"
            delivery = admin.admin.delivery(order_id, rec_ids[0])
            assert_text_contains(delivery, "操作成功")
            rec_id = rec_ids[0]

        with allure.step("前台确认收货"):
            assert_business(client.order.confirm_receipt(order_id), expected=1)

        with allure.step("评价订单"):
            resp = client.order.comment(
                order_id=order_id,
                goods_id=1,
                rec_id=rec_id,
                content=COMMON["comment"]["full_flow"],
            )
            assert_business(resp, expected=1, msg_contains="评论成功")

    def test_E2E_002_registered_user_flow(self, front):
        title("E2E-002", "已注册用户主链路：登录→加购→提交订单")
        assert_business(front.cart.add_goods(), expected=1)
        resp = front.cart.submit_order()
        assert_business(resp, expected=1)
        assert_order_sn(front.cart.extract_order_sn(resp))

    def test_E2E_003_order_pay_status_flow(self, order):
        title("E2E-003", "下单到支付链路：订单信息→货到付款→支付状态")
        client = order.account.client
        assert_html(client.cart.get_order_info(order.sn), contains=(order.sn,))
        assert_html(client.payment.pay_cod(order.id), contains=("支付",))
        assert_html(client.payment.payment_status(order.sn), contains=(order.sn,))

    def test_E2E_004_backend_fulfillment(self, admin, confirmed_order):
        title("E2E-004", "后台履约链路：确认订单→确认付款→发货")
        page = admin.admin.delivery_info(confirmed_order.id)
        rec_ids = admin.admin.extract_rec_id(page)
        assert rec_ids
        resp = admin.admin.delivery(confirmed_order.id, rec_ids[0])
        assert_text_contains(resp, "操作成功")

        detail = admin.admin.order_detail(confirmed_order.id)
        assert_no_server_error(detail)
        assert "已发货" in detail.text or "已收货" in detail.text, "后台订单详情未展示发货状态"

    def test_E2E_005_front_close_flow(self, shipped_order):
        title("E2E-005", "前台收尾链路：确认收货→评价")
        client = shipped_order.account.client
        assert_business(client.order.confirm_receipt(shipped_order.id), expected=1)
        resp = client.order.comment(
            order_id=shipped_order.id,
            goods_id=shipped_order.goods_id,
            rec_id=shipped_order.rec_id,
            content=COMMON["comment"]["logistics"],
        )
        assert_business(resp, expected=1, msg_contains="评论成功")

    # ------------------------------------------------------------ 注册/加购
    def test_E2E_007_register_then_login(self, account_factory):
        title("E2E-007", "注册后立即登录")
        account = account_factory(with_address=False)
        from api.client import ApiClient
        from utils.flow_util import login_front

        client = ApiClient()
        user_id = login_front(client, account.phone, account.password)
        assert user_id == account.user_id, "注册返回 user_id 与登录返回不一致"
        client.close()

    def test_E2E_008_register_login_add_cart(self, account_factory):
        title("E2E-008", "注册→登录→加购（未下单）")
        account = account_factory(with_address=False)
        assert_business(account.client.cart.add_goods(goods_num=E2E["add_goods_num"]), expected=1)
        page = account.client.cart.cart_page()
        assert_html(page)
        assert "购物车" in page.text

    # ------------------------------------------------------------ 一致性
    def test_E2E_009_order_sn_consistency(self, order):
        title("E2E-009", "提交订单返回值与获取订单ID 一致性")
        page = order.account.client.cart.get_order_info(order.sn)
        assert_html(page, contains=(order.sn, f'value="{order.id}"'))

    def test_E2E_010_cod_status_flow(self, admin, order):
        title("E2E-010", "货到付款后订单状态流转")
        client = order.account.client
        assert_html(client.payment.pay_cod(order.id), contains=("支付",))
        assert_business(admin.admin.pay(order.id), expected=1)
        assert_business(admin.admin.confirm(order.id), expected=1)
        # 付款+确认后才允许进入发货环节
        page = admin.admin.delivery_info(order.id)
        assert_html(page)
        assert admin.admin.extract_rec_id(page)

    def test_E2E_011_payment_status_consistency(self, order, paid_order):
        title("E2E-011", "支付状态查询与实际一致")
        assert_html(
            order.account.client.payment.payment_status(order.sn), contains=(order.sn,)
        )
        assert_html(
            paid_order.account.client.payment.payment_status(paid_order.sn),
            contains=(paid_order.sn,),
        )

    def test_E2E_012_front_status_after_delivery(self, shipped_order):
        title("E2E-012", "发货后前台订单状态同步")
        detail = shipped_order.account.client.order.order_detail(shipped_order.id)
        assert_no_server_error(detail)
        assert any(
            status in detail.text for status in E2E["order_status_words"]
        ), "前台订单详情未同步发货状态"

    # ------------------------------------------------------------ 反向/安全
    def test_E2E_013_unregistered_login(self, anon):
        title("E2E-013", "未注册账号直接登录")
        anon.user.get_login_verify()
        login = anon.user.login(username=E2E["unregistered"]["username"], password=E2E["unregistered"]["password"])
        assert_business(login, expected=-1, msg_exact="账号不存在!")

    @pytest.mark.xfail(
        reason="BUG-11：登录失败后未登录仍可加购", strict=False
    )
    def test_E2E_013b_add_after_failed_login(self, anon):
        title("E2E-013", "未注册账号登录后尝试加购")
        anon.user.get_login_verify()
        anon.user.login(username=E2E["unregistered"]["username"], password=E2E["unregistered"]["password"])
        assert_business(anon.cart.add_goods(), expected=0)

    @pytest.mark.xfail(
        reason="BUG-11：未登录可以直接加购并写入共享购物车", strict=False
    )
    def test_E2E_014_add_cart_without_login(self, anon):
        title("E2E-014", "未登录直接加购")
        assert_business(anon.cart.add_goods(), expected=0)

    @pytest.mark.xfail(
        reason="BUG-02：未支付订单可以直接后台发货", strict=False
    )
    def test_E2E_016_deliver_unpaid_order(self, admin, order):
        title("E2E-016", "未支付订单直接后台发货（跳步）")
        page = admin.admin.delivery_info(order.id)
        rec_ids = admin.admin.extract_rec_id(page)
        assert rec_ids, "未支付订单无法打开发货页"
        resp = admin.admin.delivery(order.id, rec_ids[0])
        assert "操作成功" not in resp.text

    @pytest.mark.xfail(
        reason="BUG-02：已付款但未确认的订单可以直接发货", strict=False
    )
    def test_E2E_017_deliver_unconfirmed_order(self, admin, paid_order):
        title("E2E-017", "跳过确认订单直接发货")
        page = admin.admin.delivery_info(paid_order.id)
        rec_ids = admin.admin.extract_rec_id(page)
        assert rec_ids
        resp = admin.admin.delivery(paid_order.id, rec_ids[0])
        assert "操作成功" not in resp.text

    @pytest.mark.xfail(
        reason="BUG-01：未发货订单可以直接确认收货", strict=False
    )
    def test_E2E_019_receive_unshipped_order(self, confirmed_order):
        title("E2E-019", "未发货直接确认收货")
        resp = confirmed_order.account.client.order.confirm_receipt(
            confirmed_order.id
        )
        assert_business(resp, expected=-1)

    def test_E2E_020_comment_before_receipt(self, shipped_order):
        title("E2E-020", "未确认收货直接评价")
        resp = shipped_order.account.client.order.comment(
            order_id=shipped_order.id,
            goods_id=shipped_order.goods_id,
            rec_id=shipped_order.rec_id,
            content=COMMON["comment"]["before_receipt"],
        )
        assert_no_server_error(resp)
        assert resp.json().get("status") != 1

    @pytest.mark.xfail(
        reason="BUG-08：不存在的收货地址仍能生成订单", strict=False
    )
    def test_E2E_021_order_retry_after_failure(self, buyer):
        title("E2E-021", "提交订单失败后重试")
        assert_business(buyer.client.cart.add_goods(), expected=1)
        first = buyer.client.cart.submit_order(address_id=E2E["invalid_address"])
        assert_business(first, expected=0)
        assert_business(buyer.client.cart.add_goods(), expected=1)
        second = buyer.client.cart.submit_order(address_id=buyer.address_id)
        assert_business(second, expected=1)

    def test_E2E_022_register_retry_after_captcha_error(self):
        title("E2E-022", "注册失败后重试")
        from api.client import ApiClient
        from utils.flow_util import new_phone

        client = ApiClient()
        phone = new_phone()
        client.user.get_register_verify()
        first = client.user.register(phone, COMMON["password"], verify_code="0000")
        assert_business(first, expected=-1, msg_contains="验证码")
        client.user.get_register_verify()
        second = client.user.register(phone, COMMON["password"])
        assert_business(second, expected=1)

    @pytest.mark.xfail(
        reason="BUG-05：可以为他人的订单发起支付（水平越权）", strict=False
    )
    def test_E2E_023_order_tamper_cross_user(self, account_factory, front, account):
        title("E2E-023", "链路中订单号被篡改")
        buyer = account_factory(with_address=True)
        order = place_order(buyer)
        # 查单被拒绝
        page = front.cart.get_order_info(order.sn)
        assert order.sn not in page.text
        # 支付必须校验订单归属
        pay = account.client.payment.pay_cod(order.id)
        assert order.id not in pay.text and "付款金额" not in pay.text

    def test_E2E_024_repeat_submit_one_order(self, buyer):
        title("E2E-024", "重复提交订单仅生成一单")
        assert_business(buyer.client.cart.add_goods(), expected=1)
        first = buyer.client.cart.submit_order()
        assert_business(first, expected=1)
        second = buyer.client.cart.submit_order()
        third = buyer.client.cart.submit_order()
        assert second.json().get("status") != 1
        assert third.json().get("status") != 1

    @pytest.mark.xfail(
        reason="BUG-16：重复后台付款返回成功但未变更", strict=False
    )
    def test_E2E_026_repeat_admin_pay(self, admin, paid_order):
        title("E2E-026", "后台重复确认付款")
        assert_business(admin.admin.pay(paid_order.id), expected=0)

    def test_E2E_027_repeat_receive_and_comment(self, received_order):
        title("E2E-027", "重复确认收货与重复评价")
        client = received_order.account.client
        again = client.order.confirm_receipt(received_order.id)
        assert again.json().get("status") != 1

        first = client.order.comment(
            order_id=received_order.id,
            goods_id=received_order.goods_id,
            rec_id=received_order.rec_id,
            content=COMMON["comment"]["first"],
        )
        assert first.json().get("status") == 1
        comment = client.order.comment(
            order_id=received_order.id,
            goods_id=received_order.goods_id,
            rec_id=received_order.rec_id,
            content=COMMON["comment"]["repeat"],
        )
        assert comment.json().get("status") != 1, "同一订单可重复评价"

    def test_E2E_032_pay_and_order_status(self, admin, paid_order):
        title("E2E-032", "支付状态与订单状态一致")
        detail = admin.admin.order_detail(paid_order.id)
        assert_no_server_error(detail)
        assert any(word in detail.text for word in E2E["pay_status_words"]), (
            "后台订单详情未显示已付款"
        )

    def test_E2E_033_cart_cleared_after_order(self, buyer):
        title("E2E-033", "订单提交后购物车清空")
        assert_business(buyer.client.cart.add_goods(), expected=1)
        assert_business(buyer.client.cart.submit_order(), expected=1)
        again = buyer.client.cart.submit_order()
        assert_business(again, expected=-9, msg_contains="没有选中商品")

