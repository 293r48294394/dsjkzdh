"""业务流程辅助：登录、注册新账号、建地址、下单、后台履约。

这些函数只做“造数据/走流程”，断言留给用例；失败时抛 AssertionError 并带上响应。
"""
import random
from dataclasses import dataclass, field

from api.client import ApiClient
from config.settings import settings


@dataclass
class Account:
    phone: str
    password: str
    user_id: int | None
    address_id: str | None
    client: ApiClient = field(repr=False)


@dataclass
class Order:
    sn: str
    id: str
    account: Account
    goods_id: str
    rec_id: str | None = None


def new_phone():
    """生成带测试标记的手机号（配置项 test_data.mobile_prefix + 5 位随机数）。

    统一前缀的作用：定期清理测试库时，可以按 mobile 前缀精准圈定自动化账号，
    避免误删真实用户。
    """
    prefix = str(settings.get("test_data.mobile_prefix", "199000"))
    return prefix + str(random.randint(0, 99999)).zfill(5)


def login_front(client: ApiClient, username, password):
    """前台登录：验证码一次性，必须先 GET 再 POST。"""
    client.user.get_login_verify()
    resp = client.user.login(username=username, password=password)
    body = resp.json()
    assert body.get("status") == 1, f"前台登录失败：{body}"
    return body.get("result", {}).get("user_id")


def admin_login(client: ApiClient):
    client.admin.get_verify()
    resp = client.admin.login()
    body = resp.json()
    assert body.get("status") == 1, f"后台登录失败：{body}"
    return body


def register_account(
    client: ApiClient,
    *,
    password="Abc@12345",
    with_address=False,
    consignee=None,
):
    """注册一个全新账号（必要时创建收货地址），返回 Account。

    每次重试都会重新获取验证码，避免“验证码一次性”导致误判。
    """
    last = None
    for _ in range(3):
        phone = new_phone()
        client.user.get_register_verify()
        resp = client.user.register(phone, password)
        last = resp
        try:
            body = resp.json()
        except ValueError:
            continue
        if body.get("status") == 1:
            user_id = body.get("result", {}).get("user_id")
            login_front(client, phone, password)
            address_id = None
            if with_address:
                save = client.user.add_address(mobile=phone, consignee=consignee)
                assert save.json().get("status") == 1, f"新增地址失败：{save.text}"
                ids = client.user.address_ids()
                assert ids, "新增地址后未从地址列表解析到 address_id"
                address_id = ids[0]
            return Account(phone, password, user_id, address_id, client)
    raise AssertionError(f"注册新账号失败：{getattr(last, 'text', last)}")


def place_order(account: Account, goods_num=None, goods_id=None):
    """加购并提交订单，返回 Order（含 order_sn / order_id）。"""
    assert account.address_id, "下单账号没有收货地址"
    item_ids = settings.get("goods.order_item_ids") or [
        settings.get("goods.item_id")
    ]
    random.shuffle(item_ids)
    last_add = None
    for item_id in item_ids:
        add = account.client.cart.add_goods(
            goods_num=goods_num, goods_id=goods_id, item_id=item_id
        )
        last_add = add
        if add.json().get("status") == 1:
            break
    else:
        raise AssertionError(f"加购失败（所有规格均不可用）：{last_add.text}")
    submit = account.client.cart.submit_order(address_id=account.address_id)
    body = submit.json()
    assert body.get("status") == 1, f"提交订单失败：{body}"
    sn = body.get("result")
    assert sn, f"提交订单未返回订单号：{body}"
    order_id = account.client.cart.get_order_id(sn)
    assert order_id, f"未能从订单确认页提取 order_id（order_sn={sn}）"
    return Order(
        sn=str(sn),
        id=str(order_id),
        account=account,
        goods_id=str(goods_id if goods_id is not None else settings.get("goods.goods_id")),
    )


def ship(admin: ApiClient, order: Order):
    """后台打开发货页取 rec_id 并确认发货，返回 rec_id。"""
    page = admin.admin.delivery_info(order.id)
    rec_ids = admin.admin.extract_rec_id(page)
    assert rec_ids, f"发货页未解析到 goods[]：{page.text[:300]}"
    resp = admin.admin.delivery(order.id, rec_ids[0])
    assert "操作成功" in resp.text, f"确认发货失败：{resp.text[:300]}"
    order.rec_id = rec_ids[0]
    return rec_ids[0]


def pay_and_confirm(admin: ApiClient, order: Order):
    """后台付款 → 确认订单（顺序不可反：付款会把 order_status 重置为 0）。"""
    pay = admin.admin.pay(order.id)
    assert pay.json().get("status") == 1, f"后台付款失败：{pay.text}"
    confirm = admin.admin.confirm(order.id)
    assert confirm.json().get("status") == 1, f"后台确认失败：{confirm.text}"
    return order


def confirm_receipt(order: Order):
    resp = order.account.client.order.confirm_receipt(order.id)
    body = resp.json()
    assert body.get("status") == 1, f"确认收货失败：{body}"
    return body

