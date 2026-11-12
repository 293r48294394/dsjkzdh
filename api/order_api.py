"""前台订单接口：确认收货、评价、取消（辅助）。"""
from api.base_api import BaseApi


class OrderApi(BaseApi):
    def confirm_receipt(self, order_id=None, *, omit=()):
        data = {"order_id": "" if order_id is None else str(order_id)}
        for key in omit:
            data.pop(key, None)
        return self.post_form("/index.php?m=Home&c=Order&a=order_confirm", data)

    def comment(
        self,
        order_id=None,
        goods_id=None,
        rec_id=None,
        content="自动化测试评价",
        *,
        score="5",
        goods_rank="5",
        service_rank="5",
        deliver_rank="5",
        omit=(),
    ):
        data = {
            "order_id": "" if order_id is None else str(order_id),
            "goods_id": "" if goods_id is None else str(goods_id),
            "item_id": "0",
            "prom_type": "0",
            "rec_id": "" if rec_id is None else str(rec_id),
            "score": str(score),
            "goods_rank": str(goods_rank),
            "service_rank": str(service_rank),
            "deliver_rank": str(deliver_rank),
            "content": content,
        }
        for key in omit:
            data.pop(key, None)
        return self.post_form("/index.php/Home/Order/add_comment.html", data)

    # ------------------------------------------------------ 辅助接口（非17接口）
    def cancel(self, order_id):
        """取消订单，参数名是 id（文档未给出，用于构造已取消订单）。"""
        return self.post_form(
            "/index.php?m=Home&c=Order&a=cancel_order", {"id": str(order_id)}
        )

    def order_list(self):
        return self.get("/index.php/Home/Order/order_list.html")

    def order_detail(self, order_id):
        return self.get(f"/index.php/Home/Order/order_detail/id/{order_id}.html")
