"""后台管理接口：登录、确认订单、付款、发货。"""
import re

from api.base_api import BaseApi
from config.settings import settings


class AdminApi(BaseApi):
    # ---------------------------------------------------------------- 登录
    def get_verify(self):
        return self.get("/admin/Admin/vertify")

    def login(self, username=None, password=None, verify_code=None):
        data = {
            "username": settings.get("admin.username") if username is None else str(username),
            "password": settings.get("admin.password") if password is None else str(password),
            "vertify": settings.get("verify_code") if verify_code is None else str(verify_code),
        }
        return self.post_form("/index.php?m=Admin&c=Admin&a=login", data)

    # ------------------------------------------------------------ 订单操作
    def confirm(self, order_id=None, note=""):
        data = {"note": note}
        if order_id is not None:
            url = f"/index.php/Admin/order/order_action/type/confirm?order_id={order_id}"
        else:
            url = "/index.php/Admin/order/order_action/type/confirm"
        return self.post_form(url, data)

    def pay(self, order_id=None, note=""):
        data = {"note": note}
        if order_id is not None:
            url = f"/index.php/Admin/order/order_action/type/pay?order_id={order_id}"
        else:
            url = "/index.php/Admin/order/order_action/type/pay"
        return self.post_form(url, data)

    # ---------------------------------------------------------------- 发货
    def delivery_info(self, order_id):
        return self.get(f"/index.php/admin/Order/delivery_info/order_id/{order_id}")

    @staticmethod
    def extract_rec_id(resp):
        """发货页复选框 goods[] 的 value 是 order_goods.rec_id（不是 goods_id）。"""
        return re.findall(r'name=["\']goods\[\]["\'][^>]*value=["\'](\d+)["\']', resp.text)

    def delivery(
        self,
        order_id,
        rec_id=None,
        invoice_no="12111",
        *,
        shipping="0",
        shipping_name="顺丰快递",
        shipping_code="shunfeng",
        send_type="0",
        note="自动化测试",
        omit=(),
    ):
        data = {
            "shipping": str(shipping),
            "shipping_name": shipping_name,
            "shipping_code": shipping_code,
            "send_type": str(send_type),
            "invoice_no": str(invoice_no),
            "goods[]": "" if rec_id is None else str(rec_id),
            "order_id": "" if order_id is None else str(order_id),
            "note": note,
        }
        for key in omit:
            data.pop(key, None)
        return self.post_form("/index.php/Admin/order/deliveryHandle", data)

    # ------------------------------------------------------------ 后台查询
    def order_detail(self, order_id):
        return self.get(f"/index.php/admin/Order/detail/order_id/{order_id}")

    def order_list(self):
        return self.get("/index.php/admin/Order/index")
