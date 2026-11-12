"""购物车与下单接口用例（对应 Excel CART-001 ~ CART-028）。

数据隔离：购物车相关用例全部使用“每次新注册 + 自带地址”的买家，
避免 TPshop 购物车只增不减、跨用例串数据。
参数/边界/缺陷标记统一放在 `data/cart.yaml`。
"""
import json

import allure
import pytest

from config.settings import settings
from utils.assert_util import (
    assert_business,
    assert_contract,
    assert_html,
    assert_no_server_error,
    assert_order_sn,
)
from utils.contracts import CART_ADD_SUCCESS, SUBMIT_ORDER_SUCCESS
from utils.data_util import load_data, param_cases
from utils.flow_util import place_order


FEATURE = "购物下单"
ADDRESS = settings.get("goods.address_id")
GOODS = settings.get("goods.goods_id")
ITEM = settings.get("goods.item_id")
CART = load_data("cart")


def title(case_id, text):
    allure.dynamic.title(f"{case_id} {text}")


def add_and_submit(client, **submit_kwargs):
    assert_business(client.cart.add_goods(), expected=1)
    return client.cart.submit_order(**submit_kwargs)


@allure.feature(FEATURE)
class TestCart:
    # ------------------------------------------------------------ 加购正向
    def test_CART_001_add_success(self, buyer):
        title("CART-001", "加入购物车成功")
        assert_contract(buyer.client.cart.add_goods(), CART_ADD_SUCCESS)

    # ------------------------------------------------------------ 加购反向
    def test_CART_002_goods_not_exist(self, buyer):
        case = CART["add"]["goods_not_exist"]
        title("CART-002", "商品不存在")
        resp = buyer.client.cart.add_goods(goods_id=case["goods_id"])
        assert_business(resp, expected=0, msg_exact=case["expect_msg"])

    def test_CART_003_quantity_over_limit(self, buyer):
        case = CART["add"]["over_limit"]
        title("CART-003", "购买数量超过上限 200")
        resp = buyer.client.cart.add_goods(goods_num=case["goods_num"])
        assert_business(resp, expected=0, msg_exact=case["expect_msg"])

    def test_CART_004_quantity_at_limit(self, buyer):
        case = CART["add"]["at_limit"]
        title("CART-004", "购买数量等于上限 200")
        resp = buyer.client.cart.add_goods(goods_num=case["goods_num"])
        assert_no_server_error(resp)
        body = resp.json()
        # 库存充足时加购成功；库存不足时按库存规则提示，二者都属于预期行为
        assert body.get("status") in (0, 1), f"未按库存规则处理：{body}"
        if body.get("status") == 0:
            assert "库存" in (body.get("msg") or ""), f"库存不足提示不明确：{body}"

    @pytest.mark.parametrize("case", param_cases(CART["add"]["quantity_empty"]))
    def test_CART_005_quantity_empty(self, buyer, case):
        title("CART-005", "购买数量为空")
        resp = buyer.client.cart.add_goods(**case["request"])
        assert_business(resp, expected=0, msg_exact="购买商品数量不能为0")

    @pytest.mark.parametrize("case", param_cases(CART["add"]["quantity_illegal"]))
    def test_CART_006_quantity_illegal(self, buyer, case):
        title("CART-006", f"购买数量非法值（{case['marker']}）")
        resp = buyer.client.cart.add_goods(goods_num=case["goods_num"])
        assert_no_server_error(resp)
        assert_business(resp, expected=0)

    def test_CART_006_quantity_string(self, buyer):
        case = CART["add"]["quantity_string"]
        title("CART-006", "购买数量非法值（字符串）")
        resp = buyer.client.cart.add_goods(goods_num=case["goods_num"])
        assert_business(resp, expected=0, msg_exact=case["expect_msg"])

    def test_CART_007_goods_id_missing(self, buyer):
        case = CART["add"]["goods_id_missing"]
        title("CART-007", "goods_id 缺失")
        resp = buyer.client.cart.add_goods(**case["request"])
        assert_business(resp, expected=0, msg_exact=case["expect_msg"])

    @pytest.mark.xfail(
        reason="R-05：文档声明 shop_price 必填，服务端实际不校验", strict=False
    )
    def test_CART_008_shop_price_missing(self, buyer):
        title("CART-008", "shop_price 缺失")
        resp = buyer.client.cart.add_goods()
        assert_business(resp, expected=0)

    # ------------------------------------------------------------ 安全：传价
    def test_CART_009_price_tamper(self, buyer):
        case = CART["add"]["price_tamper"]
        title("CART-009", "前端传价被篡改")
        assert_business(
            buyer.client.cart.add_goods(shop_price=case["shop_price"]), expected=1
        )
        resp = buyer.client.cart.submit_order()
        assert_business(resp, expected=1)
        sn = buyer.client.cart.extract_order_sn(resp)
        page = buyer.client.cart.get_order_info(sn)
        assert_html(page, contains=("付款金额",))
        assert "0.01" not in page.text, "服务端采用了前端传入的 0.01 价格，存在资金风险"

    # ------------------------------------------------------------ 状态/异常
    @pytest.mark.xfail(
        reason="BUG-11：未登录可以加购，并写入共享的 user_id=0 购物车", strict=False
    )
    def test_CART_011_add_without_login(self, anon):
        title("CART-011", "未登录加入购物车")
        resp = anon.cart.add_goods()
        assert_business(resp, expected=0)

    def test_CART_012_duplicate_add(self, buyer):
        case = CART["add"]["duplicate"]
        title("CART-012", "重复加购同一商品")
        for _ in range(case["times"]):
            assert_business(
                buyer.client.cart.add_goods(goods_num=case["goods_num"]), expected=1
            )
        resp = buyer.client.cart.submit_order()
        assert_business(resp, expected=1)
        assert_order_sn(buyer.client.cart.extract_order_sn(resp))

    def test_CART_013_json_content_type(self, buyer):
        title("CART-013", "Content-Type 错误（JSON）")
        resp = buyer.client.cart.post(
            "/index.php?m=Home&c=Cart&a=add",
            data=json.dumps({"goods_id": GOODS, "goods_num": 1, "item_id": ITEM}),
            headers={"Content-Type": "application/json"},
        )
        assert_no_server_error(resp)
        assert_business(resp, expected=[0, 1])

    # ------------------------------------------------------------ 下单正向
    def test_CART_014_submit_order_success(self, buyer):
        title("CART-014", "提交订单成功")
        assert_business(buyer.client.cart.add_goods(), expected=1)
        resp = buyer.client.cart.submit_order()
        assert_contract(resp, SUBMIT_ORDER_SUCCESS)
        sn = buyer.client.cart.extract_order_sn(resp)
        assert buyer.client.cart.get_order_id(sn), "订单确认页未返回 order_id"

    # ------------------------------------------------------------ 下单反向
    @pytest.mark.parametrize("case", param_cases([CART["submit"]["is_virtual_missing"]]))
    def test_CART_015_is_virtual_missing(self, buyer, case):
        title(case["id"], case["title"])
        resp = add_and_submit(buyer.client, **case["request"])
        assert_business(resp, expected=0)

    def test_CART_016_address_missing(self, buyer):
        case = CART["submit"]["address_missing"]
        title("CART-016", "address_id 缺失")
        resp = add_and_submit(buyer.client, **case["request"])
        assert_business(resp, expected=0, msg_exact=case["expect_msg"])

    @pytest.mark.parametrize("case", param_cases([CART["submit"]["address_not_exist"]]))
    def test_CART_017_address_not_exist(self, buyer, case):
        title("CART-017", case["title"])
        resp = add_and_submit(buyer.client, **case["request"])
        assert_business(resp, expected=0)

    @pytest.mark.xfail(
        reason="BUG-04：可以使用他人的收货地址下单（水平越权）", strict=False
    )
    def test_CART_017b_address_of_other_user(self, buyer):
        title("CART-017", "address_id 越权（他人地址）")
        resp = add_and_submit(buyer.client, address_id=ADDRESS)
        assert_business(resp, expected=0)

    @pytest.mark.parametrize("case", param_cases([CART["submit"]["auth_code_invalid"]]))
    def test_CART_018_auth_code_invalid(self, buyer, case):
        title(case["id"], case["title"])
        resp = add_and_submit(buyer.client, **case["request"])
        assert_business(resp, expected=0)

    @pytest.mark.parametrize("case", param_cases(CART["submit"]["take_time"]))
    def test_CART_019_take_time(self, buyer, case):
        title("CART-019", f"take_time 缺失或非法（{case['label']}）")
        resp = add_and_submit(buyer.client, **case["request"])
        assert_no_server_error(resp)
        expected = 1 if case["should_pass"] else 0
        assert resp.json().get("status") == expected, (
            f"take_time={case['label']} 期望 status={expected}，实际 {resp.json()}"
        )

    def test_CART_020_act_invalid(self, buyer):
        case = CART["submit"]["act_invalid"]
        title("CART-020", "act 取值错误")
        resp = add_and_submit(buyer.client, **case["request"])
        assert_no_server_error(resp)
        body = resp.json()
        # 实际进入“计算价格”模式：result 是价格明细，不是订单号
        assert body.get("status") == 1 and body.get("msg") == case["expect_msg"], body
        result = body.get("result")
        assert isinstance(result, dict), f"act 非 submit_order 时不应返回订单号：{result!r}"
        assert "shipping_price" in result, f"价格计算明细缺少运费字段：{result}"

    def test_CART_021_empty_cart(self, buyer):
        title("CART-021", "购物车为空提交订单")
        resp = buyer.client.cart.submit_order()
        assert_business(
            resp, expected=-9, msg_exact=CART["submit"]["empty_cart_msg"]
        )

    def test_CART_022_repeat_submit(self, buyer):
        title("CART-022", "重复提交订单")
        assert_business(buyer.client.cart.add_goods(), expected=1)
        first = buyer.client.cart.submit_order()
        assert_business(first, expected=1)
        for _ in range(CART["submit"]["repeat_times"] - 1):
            resp = buyer.client.cart.submit_order()
            assert_business(resp, expected=-9)

    def test_CART_023_submit_without_login(self, anon):
        title("CART-023", "未登录提交订单")
        resp = anon.cart.submit_order(address_id=ADDRESS)
        assert_business(resp, expected=CART["submit"]["unauth_status"])

    @pytest.mark.parametrize("case", param_cases([CART["submit"]["is_virtual_mismatch"]]))
    def test_CART_024_is_virtual_mismatch(self, buyer, case):
        title(case["id"], case["title"])
        resp = add_and_submit(buyer.client, **case["request"])
        assert_business(resp, expected=0)

    # ------------------------------------------------------------ 订单查询
    def test_CART_025_get_order_info(self, account_factory):
        title("CART-025", "按订单号获取订单信息")
        account = account_factory(with_address=True)
        order = place_order(account)
        resp = account.client.cart.get_order_info(order.sn)
        assert_html(resp, contains=(order.sn, f'value="{order.id}"'))

    @pytest.mark.parametrize("order_sn", CART["order"]["invalid_order_sns"])
    def test_CART_026_028_invalid_order_sn(self, buyer, order_sn):
        title("CART-026/028", f"订单号不存在或格式错误（{order_sn!r}）")
        resp = buyer.client.cart.get_order_info(order_sn)
        assert_no_server_error(resp)
        assert "付款金额" not in resp.text, "非法订单号仍渲染出订单支付信息"

    def test_CART_027_other_user_order(self, front, account_factory):
        title("CART-027", "查看他人订单（越权）")
        account = account_factory(with_address=True)
        order = place_order(account)
        resp = front.cart.get_order_info(order.sn)
        assert_no_server_error(resp)
        assert order.sn not in resp.text and "付款金额" not in resp.text, (
            "跨用户订单信息被泄露"
        )
