"""前台订单接口用例（对应 Excel FORDER-001 ~ FORDER-014）。"""
import allure
import pytest

from utils.assert_util import (
    assert_business,
    assert_contract,
    assert_no_server_error,
)
from utils.contracts import COMMENT_SUCCESS


FEATURE = "前台确认订单"
GOODS = 1


def title(case_id, text):
    allure.dynamic.title(f"{case_id} {text}")


def comment(order, content="自动化测试评价", **kwargs):
    return order.account.client.order.comment(
        order_id=order.id,
        goods_id=order.goods_id,
        rec_id=order.rec_id,
        content=content,
        **kwargs,
    )


@allure.feature(FEATURE)
class TestFrontOrder:
    # ------------------------------------------------------------ 确认收货
    def test_FORDER_001_confirm_receipt(self, shipped_order):
        title("FORDER-001", "前台确认收货成功")
        resp = shipped_order.account.client.order.confirm_receipt(shipped_order.id)
        assert_contract(
            resp,
            {
                "type": "object",
                "required": ["status", "msg", "url"],
                "properties": {
                    "status": {"type": "integer", "enum": [1]},
                    "msg": {"type": "string"},
                    "url": {"type": "string", "pattern": r"order_detail"},
                },
            },
        )

    def test_FORDER_002_order_id_missing(self, shipped_order):
        title("FORDER-002", "order_id 缺失")
        resp = shipped_order.account.client.order.confirm_receipt()
        assert_business(resp, expected=-1, msg_exact="该订单不能收货确认")

    def test_FORDER_003_confirm_other_user_order(self, shipped_order, account):
        title("FORDER-003", "确认收货越权")
        resp = account.client.order.confirm_receipt(shipped_order.id)
        assert_no_server_error(resp)
        assert_business(resp, expected=[-1, -2, -100])

    def test_FORDER_004_confirm_without_login(self, shipped_order, anon):
        title("FORDER-004", "未登录确认收货")
        resp = anon.order.confirm_receipt(shipped_order.id)
        assert_no_server_error(resp)
        if "json" in (resp.headers.get("Content-Type") or "").lower():
            assert resp.json().get("status") != 1
        else:
            assert "登录" in resp.text, "未登录调用确认收货既未报错也未跳转登录"

    @pytest.mark.xfail(
        reason="BUG-01：未发货订单可以直接确认收货", strict=False
    )
    def test_FORDER_005_confirm_unshipped(self, confirmed_order):
        title("FORDER-005", "对未发货订单确认收货")
        resp = confirmed_order.account.client.order.confirm_receipt(confirmed_order.id)
        assert_business(resp, expected=-1)

    def test_FORDER_006_repeat_confirm(self, shipped_order):
        title("FORDER-006", "重复确认收货")
        first = shipped_order.account.client.order.confirm_receipt(shipped_order.id)
        assert_business(first, expected=1)
        second = shipped_order.account.client.order.confirm_receipt(shipped_order.id)
        assert_no_server_error(second)
        assert second.json().get("status") != 1, "重复确认收货仍返回成功"

    # ---------------------------------------------------------------- 评价
    def test_FORDER_007_comment_success(self, received_order):
        title("FORDER-007", "评价订单成功")
        assert_contract(comment(received_order), COMMENT_SUCCESS)

    @pytest.mark.parametrize(
        "field",
        [
            pytest.param("order_id", id="FORDER-008-缺order_id"),
            pytest.param("goods_id", id="FORDER-008-缺goods_id"),
            pytest.param("goods_rank", id="FORDER-008-缺goods_rank"),
        ],
    )
    def test_FORDER_008_comment_required(self, received_order, field):
        title("FORDER-008", f"评价必填参数缺失（{field}）")
        kwargs = {"omit": (field,)}
        if field == "goods_rank":
            kwargs = {"omit": ("goods_rank",)}
        resp = received_order.account.client.order.comment(
            order_id=received_order.id,
            goods_id=received_order.goods_id,
            rec_id=received_order.rec_id,
            content="x",
            **kwargs,
        )
        assert_no_server_error(resp)
        assert resp.json().get("status") != 1, f"缺少 {field} 仍评价成功"

    @pytest.mark.xfail(
        reason="BUG-13：评价内容为空仍然评论成功", strict=False
    )
    def test_FORDER_008_content_missing(self, received_order):
        title("FORDER-008", "评价必填参数缺失（content）")
        resp = received_order.account.client.order.comment(
            order_id=received_order.id,
            goods_id=received_order.goods_id,
            rec_id=received_order.rec_id,
            omit=("content",),
        )
        assert_no_server_error(resp)
        assert resp.json().get("status") != 1

    @pytest.mark.parametrize(
        "rank,should_succeed",
        [
            pytest.param("0", False, id="FORDER-009-评分0"),
            pytest.param("1", True, id="FORDER-009-评分1"),
            pytest.param("5", True, id="FORDER-009-评分5"),
            pytest.param(
                "6",
                False,
                id="FORDER-009-评分6",
                marks=pytest.mark.xfail(
                    reason="BUG-12：评分 6 未被拒绝，直接落库", strict=False
                ),
            ),
        ],
    )
    def test_FORDER_009_rank_boundary(self, received_order, rank, should_succeed):
        title("FORDER-009", f"评分等级边界（{rank}）")
        resp = comment(received_order, goods_rank=rank)
        assert_no_server_error(resp)
        status = resp.json().get("status")
        if should_succeed:
            assert status == 1, f"评分合法却提交失败：{resp.text}"
        else:
            assert status != 1, f"非法评分未被拒绝：{resp.text}"


    @pytest.mark.parametrize(
        "content,label,should_succeed",
        [
            pytest.param(
                "",
                "空串",
                False,
                id="FORDER-010-空串",
                marks=pytest.mark.xfail(reason="BUG-13：空评价仍成功", strict=False),
            ),
            pytest.param(
                "测" * 2000,
                "2000字",
                False,
                id="FORDER-010-超长",
                marks=pytest.mark.xfail(reason="R-02：评价内容无长度限制", strict=False),
            ),
            pytest.param(
                "   ",
                "纯空格",
                False,
                id="FORDER-010-纯空格",
                marks=pytest.mark.xfail(reason="新缺陷：纯空格评价仍成功", strict=False),
            ),
        ],
    )
    def test_FORDER_010_content_boundary(self, received_order, content, label, should_succeed):
        title("FORDER-010", f"评价内容边界（{label}）")
        resp = comment(received_order, content=content)
        assert_no_server_error(resp)
        status = resp.json().get("status")
        if should_succeed:
            assert status == 1, f"评分合法却提交失败：{resp.text}"
        else:
            assert status != 1, f"非法评分未被拒绝：{resp.text}"

    def test_FORDER_011_content_xss(self, received_order):
        title("FORDER-011", "评价内容 XSS")
        payload = "<script>alert(1)</script>"
        resp = comment(received_order, content=payload)
        assert_business(resp, expected=1)
        detail = received_order.account.client.order.order_detail(received_order.id)
        assert_no_server_error(detail)
        assert payload not in detail.text, "评价内容中的脚本被原样输出"
        assert "alert(1)" not in detail.text, "评价内容中的脚本在订单详情页被回显"

    def test_FORDER_012_comment_without_login(self, received_order, anon):
        title("FORDER-012", "未登录评价")
        resp = anon.order.comment(
            received_order.id, received_order.goods_id, received_order.rec_id, "x"
        )
        assert_no_server_error(resp)
        if "json" in (resp.headers.get("Content-Type") or "").lower():
            assert resp.json().get("status") != 1
        else:
            assert "登录" in resp.text

    def test_FORDER_013_comment_before_receipt(self, shipped_order):
        title("FORDER-013", "对未收货订单评价")
        resp = shipped_order.account.client.order.comment(
            order_id=shipped_order.id,
            goods_id=shipped_order.goods_id,
            rec_id=shipped_order.rec_id,
            content="未收货评价",
        )
        assert_no_server_error(resp)
        assert resp.json().get("status") != 1, "未确认收货仍可评价"

    def test_FORDER_014_repeat_comment(self, commented_order):
        title("FORDER-014", "重复评价同一订单")
        resp = commented_order.account.client.order.comment(
            order_id=commented_order.id,
            goods_id=commented_order.goods_id,
            rec_id=commented_order.rec_id,
            content="第二次评价",
        )
        assert_no_server_error(resp)
        assert resp.json().get("status") != 1, "同一订单可重复评价"



