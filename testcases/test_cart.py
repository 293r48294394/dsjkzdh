"""购物车与下单接口用例（对应 Excel CART-001 ~ CART-028）。

数据隔离：购物车相关用例全部使用“每次新注册 + 自带地址”的买家，
避免 TPshop 购物车只增不减、跨用例串数据。
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
from utils.flow_util import place_order


FEATURE = "购物下单"
ADDRESS = settings.get("goods.address_id")
GOODS = settings.get("goods.goods_id")
ITEM = settings.get("goods.item_id")


def title(case_id, text):
    allure.dynamic.title(f"{case_id} {text}")


def add(client, **kwargs):
    return client.cart.add_goods(**kwargs)


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
        title("CART-002", "商品不存在")
        resp = buyer.client.cart.add_goods(goods_id=999999)
        assert_business(resp, expected=0, msg_exact="购买商品不存在")

    def test_CART_003_quantity_over_limit(self, buyer):
        title("CART-003", "购买数量超过上限 200")
        resp = buyer.client.cart.add_goods(goods_num=201)
        assert_business(resp, expected=0, msg_exact="购买商品数量大于200")

    def test_CART_004_quantity_at_limit(self, buyer):
        title("CART-004", "购买数量等于上限 200")
        resp = buyer.client.cart.add_goods(goods_num=200)
        assert_no_server_error(resp)
        body = resp.json()
        # 库存充足时加购成功；库存不足时按库存规则提示，二者都属于预期行为
        assert body.get("status") in (0, 1), f"未按库存规则处理：{body}"
        if body.get("status") == 0:
            assert "库存" in (body.get("msg") or ""), f"库存不足提示不明确：{body}"

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param(dict(omit=("goods_num",)), id="CART-005-数量缺失"),
            pytest.param(dict(goods_num=0), id="CART-005-数量为0"),
        ],
    )
    def test_CART_005_quantity_empty(self, buyer, kwargs):
        title("CART-005", "购买数量为空")
        resp = buyer.client.cart.add_goods(**kwargs)
        assert_business(resp, expected=0, msg_exact="购买商品数量不能为0")

    @pytest.mark.parametrize(
        "goods_num,marker",
        [
            pytest.param(
                -1,
                "负数",
                id="CART-006-负数",
                marks=pytest.mark.xfail(
                    reason="BUG-14：负数购买数量加购成功并落库为 0", strict=False
                ),
            ),
            pytest.param(
                1.5,
                "小数",
                id="CART-006-小数",
                marks=pytest.mark.xfail(
                    reason="新缺陷：小数数量未拒绝，被按整数处理", strict=False
                ),
            ),
        ],
    )
    def test_CART_006_quantity_illegal(self, buyer, goods_num, marker):
        title("CART-006", f"购买数量非法值（{marker}）")
        resp = buyer.client.cart.add_goods(goods_num=goods_num)
        assert_no_server_error(resp)
        assert_business(resp, expected=0)

    def test_CART_006_quantity_string(self, buyer):
        title("CART-006", "购买数量非法值（字符串）")
        resp = buyer.client.cart.add_goods(goods_num="abc")
        assert_business(resp, expected=0, msg_exact="购买商品数量不能为0")

    def test_CART_007_goods_id_missing(self, buyer):
        title("CART-007", "goods_id 缺失")
        resp = buyer.client.cart.add_goods(omit=("goods_id",))
        assert_business(resp, expected=0, msg_exact="请选择要购买的商品")

    @pytest.mark.xfail(
        reason="R-05：文档声明 shop_price 必填，服务端实际不校验", strict=False
    )
    def test_CART_008_shop_price_missing(self, buyer):
        title("CART-008", "shop_price 缺失")
        resp = buyer.client.cart.add_goods()
        assert_business(resp, expected=0)

    # ------------------------------------------------------------ 安全：传价
    def test_CART_009_price_tamper(self, buyer):
        title("CART-009", "前端传价被篡改")
        assert_business(buyer.client.cart.add_goods(shop_price="0.01"), expected=1)
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
        title("CART-012", "重复加购同一商品")
        assert_business(buyer.client.cart.add_goods(goods_num=1), expected=1)
        assert_business(buyer.client.cart.add_goods(goods_num=1), expected=1)
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
    @pytest.mark.xfail(
        reason="新缺陷：提交订单未校验 is_virtual，缺失仍可下单", strict=False
    )
    def test_CART_015_is_virtual_missing(self, buyer):
        title("CART-015", "is_virtual 缺失")
        resp = add_and_submit(buyer.client, omit=("is_virtual",))
        assert_business(resp, expected=0)

    def test_CART_016_address_missing(self, buyer):
        title("CART-016", "address_id 缺失")
        resp = add_and_submit(buyer.client, omit=("address_id",))
        assert_business(resp, expected=0, msg_exact="请先填写收货人信息")

    @pytest.mark.xfail(
        reason="BUG-08：不存在的收货地址仍能生成订单", strict=False
    )
    def test_CART_017_address_not_exist(self, buyer):
        title("CART-017", "address_id 不存在")
        resp = add_and_submit(buyer.client, address_id=999999)
        assert_business(resp, expected=0)

    @pytest.mark.xfail(
        reason="BUG-04：可以使用他人的收货地址下单（水平越权）", strict=False
    )
    def test_CART_017b_address_of_other_user(self, buyer):
        title("CART-017", "address_id 越权（他人地址）")
        resp = add_and_submit(buyer.client, address_id=ADDRESS)
        assert_business(resp, expected=0)

    @pytest.mark.xfail(
        reason="BUG-15：提交订单的 auth_code 未被校验", strict=False
    )
    def test_CART_018_auth_code_invalid(self, buyer):
        title("CART-018", "auth_code 取值错误")
        resp = add_and_submit(buyer.client, auth_code="TEST")
        assert_business(resp, expected=0)

    @pytest.mark.parametrize(
        "kwargs,label,should_pass",
        [
            pytest.param(dict(omit=("take_time",)), "缺省", True, id="CART-019-缺省"),
            pytest.param(
                dict(take_time="abc"),
                "非时间戳",
                False,
                id="CART-019-非时间戳",
                marks=pytest.mark.xfail(
                    reason="新缺陷：take_time 非时间戳未被拒绝", strict=False
                ),
            ),
            pytest.param(
                dict(take_time="1000000000"),
                "过去时间",
                False,
                id="CART-019-过去",
                marks=pytest.mark.xfail(
                    reason="新缺陷：take_time 过去时间未被拒绝", strict=False
                ),
            ),
            pytest.param(
                dict(take_time="9999999999"),
                "未来时间",
                False,
                id="CART-019-未来",
                marks=pytest.mark.xfail(
                    reason="新缺陷：take_time 未来时间未被拒绝", strict=False
                ),
            ),
        ],
    )
    def test_CART_019_take_time(self, buyer, kwargs, label, should_pass):
        title("CART-019", f"take_time 缺失或非法（{label}）")
        resp = add_and_submit(buyer.client, **kwargs)
        assert_no_server_error(resp)
        expected = 1 if should_pass else 0
        assert resp.json().get("status") == expected, (
            f"take_time={label} 期望 status={expected}，实际 {resp.json()}"
        )

    def test_CART_020_act_invalid(self, buyer):
        title("CART-020", "act 取值错误")
        resp = add_and_submit(buyer.client, act="submit")
        assert_no_server_error(resp)
        body = resp.json()
        # 实际进入“计算价格”模式：result 是价格明细，不是订单号
        assert body.get("status") == 1 and body.get("msg") == "计算成功", body
        result = body.get("result")
        assert isinstance(result, dict), f"act 非 submit_order 时不应返回订单号：{result!r}"
        assert "shipping_price" in result, f"价格计算明细缺少运费字段：{result}"

    def test_CART_021_empty_cart(self, buyer):
        title("CART-021", "购物车为空提交订单")
        resp = buyer.client.cart.submit_order()
        assert_business(resp, expected=-9, msg_exact="你的购物车没有选中商品")

    def test_CART_022_repeat_submit(self, buyer):
        title("CART-022", "重复提交订单")
        assert_business(buyer.client.cart.add_goods(), expected=1)
        first = buyer.client.cart.submit_order()
        assert_business(first, expected=1)
        second = buyer.client.cart.submit_order()
        third = buyer.client.cart.submit_order()
        assert_business(second, expected=-9)
        assert_business(third, expected=-9)

    def test_CART_023_submit_without_login(self, anon):
        title("CART-023", "未登录提交订单")
        resp = anon.cart.submit_order(address_id=ADDRESS)
        assert_business(resp, expected=-100)

    @pytest.mark.xfail(
        reason="新缺陷：is_virtual 与实际商品类型不符仍可下单", strict=False
    )
    def test_CART_024_is_virtual_mismatch(self, buyer):
        title("CART-024", "is_virtual 与实际商品类型不符")
        resp = add_and_submit(buyer.client, is_virtual="1")
        assert_business(resp, expected=0)

    # ------------------------------------------------------------ 订单查询
    def test_CART_025_get_order_info(self, account_factory):
        title("CART-025", "按订单号获取订单信息")
        account = account_factory(with_address=True)
        order = place_order(account)
        resp = account.client.cart.get_order_info(order.sn)
        assert_html(resp, contains=(order.sn, f'value="{order.id}"'))

    @pytest.mark.parametrize("order_sn", ["202299999999999999", "abc", ""])
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
