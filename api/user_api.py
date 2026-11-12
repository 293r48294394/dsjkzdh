"""前台用户接口：验证码、注册、登录、收货地址（辅助数据构造接口）。"""
import re

from api.base_api import BaseApi
from config.settings import settings
from utils.crypto_util import encrypt_password


class UserApi(BaseApi):
    # ------------------------------------------------------------ 图形验证码
    def get_login_verify(self):
        """获取登录图片验证码（GET 后验证码写入当前会话，一次性）。"""
        return self.get("/index.php?m=Home&c=User&a=verify")

    def get_register_verify(self):
        """获取注册图片验证码。"""
        return self.get("/index.php/Home/User/verify/type/user_reg.html")

    # ---------------------------------------------------------------- 注册
    def register(
        self,
        username,
        password,
        verify_code=None,
        *,
        password2=None,
        auth_code="TPSHOP",
        scene="1",
        invite="",
        omit=(),
    ):
        """注册。

        :param password: 明文密码，提交前按 TPshop 规则 md5('TPSHOP' + 明文)
        :param password2: 第二次密码（明文），默认与 password 相同
        :param omit: 需要从表单中移除的字段，如 ("auth_code",)
        """
        encrypted = encrypt_password(password) if password is not None else ""
        data = {
            "auth_code": auth_code,
            "scene": str(scene),
            "username": "" if username is None else str(username),
            "verify_code": settings.get("verify_code") if verify_code is None else str(verify_code),
            "password": encrypted if password is not None else "",
            "password2": encrypt_password(password2) if password2 is not None else encrypted,
            "invite": "" if invite is None else str(invite),
        }
        for key in omit:
            data.pop(key, None)
        return self.post_form("/Home/User/reg.html", data)

    # ---------------------------------------------------------------- 登录
    def login(self, username=None, password=None, verify_code=None, t="0.123456"):
        """登录。password 传明文（文档明示）。username/password 传空串表示“值传空”。"""
        data = {
            "username": settings.get("front.username") if username is None else str(username),
            "password": settings.get("front.password") if password is None else str(password),
            "verify_code": settings.get("verify_code") if verify_code is None else str(verify_code),
        }
        return self.post_form(f"/index.php?m=Home&c=User&a=do_login&t={t}", data)

    # ------------------------------------------------------------ 收货地址
    def add_address(
        self,
        mobile,
        consignee=None,
        province=None,
        city=None,
        district=None,
        twon=None,
        detail=None,
        zipcode=None,
    ):
        """新增收货地址（辅助接口，不在 17 个被测接口内，用于构造新用户下单数据）。"""
        cfg = settings
        data = {
            "address_id": "0",
            "consignee": consignee or cfg.get("address.consignee"),
            "mobile": str(mobile),
            "province": str(province if province is not None else cfg.get("address.province")),
            "city": str(city if city is not None else cfg.get("address.city")),
            "district": str(district if district is not None else cfg.get("address.district")),
            "twon": str(twon if twon is not None else cfg.get("address.twon")),
            "address": detail or cfg.get("address.detail"),
            "zipcode": zipcode or cfg.get("address.zipcode"),
            "is_default": "1",
        }
        return self.post_form("/index.php/Home/User/addressSave.html", data)

    def address_list(self):
        return self.get("/index.php/Home/User/address_list.html")

    def address_ids(self):
        """从地址列表页解析 address_id（同一地址在 PC/移动端模板会重复出现，去重）。"""
        html = self.address_list().text
        ids = re.findall(r'data-address-id="(\d+)"', html)
        return list(dict.fromkeys(ids))
