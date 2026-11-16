# data 目录

按模块拆分的 YAML 测试数据，由 `utils/data_util.py` 读取。

## 文件

| 文件 | 内容 |
|---|---|
| common.yaml | 共用密码、评价内容 |
| auth.yaml | 注册/登录的非法输入、必填缺失、密码长度、错误码 |
| cart.yaml | 加购/下单的数量、地址、take_time、订单号边界 |
| payment.yaml | pay_radio、order_id、master_order_sn 异常值 |
| admin_login.yaml | 后台登录错误参数、验证码类型 |
| admin_order.yaml | note、发货必填、invoice_no 边界 |
| front_order.yaml | 评价必填、评分、内容边界、XSS |
| e2e.yaml | 全链路公用账号、地址、状态关键字 |

## 用例字段

```yaml
- id: CART-019-非时间戳      # 必填，pytest 用例 ID
  request: {take_time: abc}  # 直接展开为接口参数
  label: 非时间戳            # 报告/标题用
  should_pass: false         # 自定义断言字段
  bug: "新缺陷：..."         # 可选，填了自动 xfail
```

长文本不要直接贴：

```yaml
repeat:
  char: "测"
  times: 2000
```

测试里用 `expand_text(case["repeat"])` 展开。

## 约定

- `config/config.yaml` 只放环境相关配置（地址、账号、商品、验证码、清理前缀）；
- 测试输入、边界值、预期业务码/提示、缺陷标记放这里；
- 参数化用例统一用 `param_cases()` 生成 `pytest.param`，保证 ID 与 Excel 编号一致；
- 已修复的缺陷：删掉 `bug` 字段，用例恢复普通断言，XPASS 会提醒回归。
