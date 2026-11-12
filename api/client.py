"""接口客户端：把同一会话下的各模块 API 组合在一起。

每个 ApiClient 持有独立 requests.Session，代表一个“登录用户/匿名访客”。
"""
import requests

from api.admin_api import AdminApi
from api.cart_api import CartApi
from api.order_api import OrderApi
from api.payment_api import PaymentApi
from api.user_api import UserApi


class ApiClient:
    def __init__(self, session=None):
        self.session = session if session is not None else requests.Session()
        self.user = UserApi(self.session)
        self.cart = CartApi(self.session)
        self.payment = PaymentApi(self.session)
        self.order = OrderApi(self.session)
        self.admin = AdminApi(self.session)

    def close(self):
        self.session.close()

    def __repr__(self):
        return f"<ApiClient cookies={self.session.cookies.get_dict()}>"
