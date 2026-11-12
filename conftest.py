"""全局 fixture。

分层：
- 会话级：front（主账号登录态）、admin（后台登录态），只登录一次，减少验证码开销；
- 函数级：anon / buyer / account 每次全新会话，保证购物车、登录态互不污染；
- 订单级：order → paid_order → confirmed_order → shipped_order → received_order，
  按 TPshop 真实状态机“后台付款 → 确认 → 发货 → 前台收货”逐级构造。
"""
import pytest

from api.client import ApiClient
from config.settings import settings
from utils.flow_util import (
    admin_login,
    confirm_receipt,
    login_front,
    pay_and_confirm,
    place_order,
    register_account,
    ship,
)


# ------------------------------------------------------------------ 会话级
@pytest.fixture(scope="session")
def front():
    """前台主账号（13812000001，自带地址 135），用于跨用户/越权类用例。"""
    client = ApiClient()
    login_front(client, settings.get("front.username"), settings.get("front.password"))
    yield client
    client.close()


@pytest.fixture(scope="session")
def admin():
    """后台管理员登录态。"""
    client = ApiClient()
    admin_login(client)
    yield client
    client.close()


# ------------------------------------------------------------------ 函数级
@pytest.fixture
def anon():
    """全新匿名会话（无任何 Cookie）。"""
    client = ApiClient()
    yield client
    client.close()


@pytest.fixture
def account_factory():
    """新账号工厂：每个账号独立会话，可自动创建收货地址。"""
    clients = []

    def _make(with_address=False):
        client = ApiClient()
        clients.append(client)
        return register_account(client, with_address=with_address)

    yield _make
    for client in clients:
        client.close()


@pytest.fixture
def buyer(account_factory):
    """已登录 + 已有收货地址的全新买家（购物车为空）。"""
    return account_factory(with_address=True)


@pytest.fixture
def account(account_factory):
    """已登录但没有收货地址的全新账号。"""
    return account_factory(with_address=False)


# ------------------------------------------------------------------ 订单级
@pytest.fixture
def make_order(buyer, admin):
    """按需创建订单，可指定购买数量。"""

    def _make(goods_num=None):
        return place_order(buyer, goods_num=goods_num)

    return _make


@pytest.fixture
def order(buyer):
    """新建一笔待付款、待确认订单。"""
    return place_order(buyer)


@pytest.fixture
def paid_order(order, admin):
    """后台已确认付款（order_status 会被重置为 0，pay_status=1）。"""
    resp = admin.admin.pay(order.id)
    assert resp.json().get("status") == 1, f"后台付款失败：{resp.text}"
    return order


@pytest.fixture
def confirmed_order(paid_order, admin):
    """后台已付款 + 已确认，处于待发货。"""
    resp = admin.admin.confirm(paid_order.id)
    assert resp.json().get("status") == 1, f"后台确认失败：{resp.text}"
    return paid_order


@pytest.fixture
def shipped_order(confirmed_order, admin):
    """后台已完成发货，前台处于待收货。"""
    ship(admin, confirmed_order)
    return confirmed_order


@pytest.fixture
def received_order(shipped_order):
    """前台已确认收货，处于待评价。"""
    confirm_receipt(shipped_order)
    return shipped_order


@pytest.fixture
def commented_order(received_order):
    """已完成评价，订单终态。"""
    account = received_order.account
    resp = account.client.order.comment(
        order_id=received_order.id,
        goods_id=received_order.goods_id,
        rec_id=received_order.rec_id,
        content="自动化测试评价",
    )
    assert resp.json().get("status") == 1, f"评价失败：{resp.text}"
    return received_order


@pytest.fixture
def fulfilled_order(confirmed_order, admin):
    """付款 + 确认（供发货失败/跳步类用例复用）。"""
    return pay_and_confirm(admin, confirmed_order)
