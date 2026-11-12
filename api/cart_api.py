"""购物车与下单接口。"""
import re
import time

from api.base_api import BaseApi
from config.settings import settings


class CartApi(BaseApi):
    # ------------------------------------------------------------ 加入购物车
    def add_goods(
        self,
        goods_id=None,
        goods_num=None,
        item_id=None,
        *,
        shop_price=None,
        store_count=None,
        omit=(),
    ):
        """加购。

        shop_price / store_count 仅用于“前端传价/传库存被篡改”安全用例，
        服务端正常只读取 goods_id / goods_num / item_id。
        """
        data = {
            "goods_id": str(settings.get("goods.goods_id") if goods_id is None else goods_id),
            "goods_num": str(settings.get("goods.num", 1) if goods_num is None else goods_num),
            "item_id": str(settings.get("goods.item_id") if item_id is None else item_id),
        }
        if shop_price is not None:
            data["shop_price"] = str(shop_price)
        if store_count is not None:
            data["store_count"] = str(store_count)
        for key in omit:
            data.pop(key, None)
        return self.post_form("/index.php?m=Home&c=Cart&a=add", data)

    # ---------------------------------------------------------------- 下单
    def submit_order(
        self,
        address_id=None,
        *,
        is_virtual="0",
        auth_code=None,
        take_time=None,
        act="submit_order",
        omit=(),
    ):
        data = {
            "is_virtual": str(is_virtual),
            "address_id": str(settings.get("goods.address_id") if address_id is None else address_id),
            "auth_code": settings.get("goods.auth_code") if auth_code is None else str(auth_code),
            "take_time": str(int(time.time()) if take_time is None else take_time),
            "act": str(act),
        }
        for key in omit:
            data.pop(key, None)
        return self.post_form("/Home/Cart/cart3.html", data)

    # ------------------------------------------------------------ 订单查询
    @staticmethod
    def extract_order_sn(resp):
        """提交订单成功时 result 字段就是订单号。"""
        try:
            return resp.json().get("result")
        except ValueError:
            return None

    def get_order_info(self, order_sn):
        """按订单号获取订单确认页（HTML）。"""
        return self.get(f"/index.php?m=Home&c=Cart&a=cart4&order_sn={order_sn}")

    def get_order_id(self, order_sn):
        """从订单确认页隐藏域提取 order_id。"""
        resp = self.get_order_info(order_sn)
        matched = re.search(r'name=["\']order_id["\'][^>]*value=["\'](\d+)["\']', resp.text)
        return matched.group(1) if matched else None

    def cart_page(self):
        return self.get("/index.php?m=Home&c=Cart&a=index")

    @staticmethod
    def cart_goods_total(html):
        """从购物车页面粗略解析商品件数（用于“加购是否累加/下单是否清空”断言）。"""
        # TPshop 购物车页有 "共X件商品" 文案
        matched = re.search(r"共\s*<em>(\d+)</em>\s*件", html) or re.search(r"共(\d+)件", html)
        return int(matched.group(1)) if matched else None
