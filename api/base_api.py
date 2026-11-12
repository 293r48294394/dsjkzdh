"""所有接口对象的基类：每个实例持有独立会话，统一请求入口与响应记录。

设计要点：
- **实例级 Session**：前台用户、后台管理员、匿名会话、每个新注册用户各自独立，
  避免旧框架“类级共享 Session”导致的串号问题（登录态会互相覆盖）。
- 请求/响应自动写入 Allure；图片等二进制响应只记录元信息，避免报告膨胀。
"""
import allure
import requests

from config.settings import settings


class BaseApi:
    def __init__(self, session=None, base_url=None, timeout=None):
        self.session = session if session is not None else requests.Session()
        self.base_url = (base_url or settings.get("base_url")).rstrip("/")
        self.timeout = timeout or settings.get("timeout", 10)

    # ------------------------------------------------------------------ 请求
    def request(self, method, path, **kwargs):
        url = path if str(path).startswith("http") else f"{self.base_url}/{str(path).lstrip('/')}"
        kwargs.setdefault("timeout", self.timeout)
        resp = self.session.request(method, url, **kwargs)
        self._attach(method, url, kwargs, resp)
        return resp

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, data=None, **kwargs):
        return self.request("POST", path, data=data, **kwargs)

    def post_form(self, path, data, **kwargs):
        return self.request("POST", path, data=data, **kwargs)

    # ------------------------------------------------------------------ 报告
    @staticmethod
    def _attach(method, url, kwargs, resp):
        payload = kwargs.get("data") or kwargs.get("json") or kwargs.get("params")
        content_type = (resp.headers.get("Content-Type") or "").lower()
        allure.attach(
            f"{method} {url}\nparams/data: {payload}",
            name="request",
            attachment_type=allure.attachment_type.TEXT,
        )
        if "image" in content_type:
            body = f"<binary image> content-type={content_type} bytes={len(resp.content)}"
        else:
            body = resp.text
        allure.attach(body, name="response", attachment_type=allure.attachment_type.TEXT)

    # ------------------------------------------------------------------ 工具
    def cookies(self):
        return self.session.cookies.get_dict()

    def reset_cookies(self):
        self.session.cookies.clear()
