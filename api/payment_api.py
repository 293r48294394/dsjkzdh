"""支付相关接口（本环境仅货到付款 cod，属于伪支付）。"""
from api.base_api import BaseApi


class PaymentApi(BaseApi):
    def pay_cod(self, order_id=None, *, pay_radio="pay_code=cod", master_order_sn="", omit=()):
        data = {
            "pay_radio": pay_radio,
            "order_id": "" if order_id is None else str(order_id),
            "master_order_sn": master_order_sn,
        }
        for key in omit:
            data.pop(key, None)
        return self.post_form("/index.php/Home/Payment/getCode.html", data)

    def payment_status(self, order_sn):
        """查看支付状态页：静态回显订单号，不能作为支付成功判据。"""
        return self.get(f"/index.php/home/Payment/returnUrl/pay_code/cod/order_sn/{order_sn}.html")
