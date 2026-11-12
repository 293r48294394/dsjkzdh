"""TPshop 密码加密工具。"""
import hashlib


AUTH_CODE = "TPSHOP"


def encrypt_password(plain):
    """注册接口密码规则：md5('TPSHOP' + 明文密码)。"""
    return hashlib.md5((AUTH_CODE + plain).encode("utf-8")).hexdigest()
