# TPshop 接口自动化测试框架

基于 `Python + Pytest + Requests + Allure` 的接口自动化回归工程，覆盖 TPshop 文档中的 17 个接口、7 个业务模块。

按《接口测试用例_TPSHOP接口文档V1.0_20261016.xlsx》全部 157 条用例重新评估后，落地 **137 条自动化用例**（99 条稳定通过、37 条缺陷回归、1 条合并），其余 20 条因依赖 DB/产品口径/并发压测/真实验证码环境，未纳入纯接口回归。

- 评估矩阵：`E:\codex\测试用例\output\接口测试用例_自动化评估_20261110.xlsx`
- 评估报告：`E:\codex\测试用例\output\接口自动化评估报告_20261110.md`

## 目录结构

```text
pythonProject5/
├── config/
│   ├── config.yaml          # 环境、账号、商品/规格、地址参数
│   ├── settings.py          # 点号取值（settings.get("front.username")）
│   └── db.example.yaml      # 测试库连接示例，复制为 db.yaml
├── api/                     # API Object 层
│   ├── base_api.py          # 实例级 Session、统一请求/Allure 记录
│   ├── client.py            # ApiClient：同一会话下的各模块 API 组合
│   ├── user_api.py          # 验证码、注册、登录、地址（辅助造数）
│   ├── cart_api.py          # 加购、下单、订单确认页
│   ├── payment_api.py       # 货到付款、支付状态页
│   ├── order_api.py         # 确认收货、评价、取消（辅助）
│   └── admin_api.py         # 后台登录、确认、付款、发货
├── testcases/               # 用例（按模块拆分）
│   ├── test_auth.py
│   ├── test_cart.py
│   ├── test_payment.py
│   ├── test_admin_login.py
│   ├── test_admin_order.py
│   ├── test_front_order.py
│   └── test_e2e.py
├── utils/
│   ├── flow_util.py         # 注册新账号、建地址、下单、发货等业务流
│   ├── assert_util.py       # HTTP/业务码/页面/图片/异常信息断言
│   ├── contract_util.py     # 轻量 JSON Schema 校验（无第三方依赖）
│   ├── contracts.py         # 各接口成功响应契约
│   └── crypto_util.py       # md5('TPSHOP' + 明文)
├── tools/
│   └── clean_test_data.py   # 测试数据定期清理（默认 dry-run）
├── conftest.py              # 会话级/账号级/订单状态机 fixture
├── pytest.ini
├── requirements.txt
└── README.md
```

## 用例覆盖

| 测试文件 | 覆盖 Excel 用例 | 用例项 | passed | xfailed |
|---|---|---:|---:|---:|
| test_auth.py | AUTH-001 ~ AUTH-036（除 020/027/037/038） | 46 | 38 | 8 |
| test_cart.py | CART-001 ~ CART-028（除 010） | 35 | 23 | 12 |
| test_payment.py | PAY-001 ~ PAY-012 | 13 | 10 | 3 |
| test_admin_login.py | ADMLOGIN-001 ~ ADMLOGIN-011（除 009） | 12 | 12 | 0 |
| test_admin_order.py | ADMORDER-001 ~ ADMORDER-018 | 21 | 11 | 10 |
| test_front_order.py | FORDER-001 ~ FORDER-014 | 22 | 16 | 6 |
| test_e2e.py | E2E-001 ~ E2E-033（可自动化部分） | 26 | 18 | 8 |
| **合计** | **137 条用例落地** | **175** | **128** | **47** |

> 用例项 175 > 用例 137，是因为参数化（密码 5/6/16/17 位、评分 0/1/5/6、订单号缺失/非法等）和 E2E-013 拆成两条。

全量运行约 2 分钟。

## 快速开始

```bash
pip install -r requirements.txt

pytest                          # 全量回归
pytest -m smoke                 # 冒烟（E2E-001 主链路）
pytest --collect-only           # 只收集
allure serve report/result      # 打开报告
```

## 关键设计

### 1. 实例级 Session，避免串号

每个 `ApiClient` 持有独立的 `requests.Session`：前台主账号、后台管理员、匿名会话、每个新注册用户互不影响。旧版用类属性共享 Session，注册反向用例会被“注册成功后自动登录”重定向，这是旧套件 3 条失败的主因。

### 2. 数据自造自清，按账号隔离

- 购物车用例：每个用例新注册一个买家，并自动创建收货地址（辅助接口 `addressSave`，不在 17 个被测接口内），避免 TPshop 购物车只增不减造成串数据。
- 订单用例：`place_order()` 负责加购 + 下单 + 从 `cart4` 页面提取 `order_id`。
- 下单规格使用库存轮换池（`goods.order_item_ids`），避免把一个规格的库存打空。

### 3. 订单状态机 fixture

TPshop 后台付款会把 `order_status` 重置为 0，正确顺序是：

```text
付款 → 确认订单 → 发货 → 前台确认收货 → 评价
```

`conftest.py` 提供五级 fixture：

```text
order → paid_order → confirmed_order → shipped_order → received_order → commented_order
```

用例只声明所需状态，不重复编排。

### 4. 契约校验 + 明确断言

- 成功响应统一校验 `status / msg / result` 的字段、类型、格式（如订单号 `^\d{14,20}$`）。
- 反向用例断言具体业务码与提示，而不是只断言“非 200”。
- 页面类接口断言关键元素（订单号、`order_id` 隐藏域、发货页 `goods[]`）。

### 5. 已知缺陷用 xfail 管理

```python
@pytest.mark.xfail(reason="BUG-01：未发货订单可以直接确认收货", strict=False)
def test_FORDER_005_confirm_unshipped(self, confirmed_order):
    ...
```

- 缺陷未修复：用例 xfail，流水线保持绿色；
- 缺陷修复：用例 XPASS，报告直接提示，随后把标记改回普通用例；
- `strict=False` 防止“修复后反而把流水线打红”。

37 条缺陷用例（参数化后共 47 个 xfail 用例项）对应 BUG-01 ~ BUG-17 及本轮新发现的 13 个问题，详见评估报告。

## TPshop 环境注意点

- `config.yaml` 的账号/商品/地址必须与目标环境一致；Excel 中的 `324 / 135 / HM_2023_test` 只是文档示例值，本环境实际是 `goods_id=1`、`address_id=135`、后台密码 `123456`。
- 验证码固定 `8888`，且**一次性**：每次登录/注册前都要先 GET 对应验证码接口。
- 货到付款是伪支付：`getCode` 只写 `pay_code`，`pay_status` 仍为 0，真正付款动作在后台“订单付款”。
- 后台付款会把订单状态重置为 0，必须“先付款、再确认、后发货”。
- 确认发货字段是 `goods[]=<order_goods.rec_id>`，不是 `goods_id`。
- “查看支付状态”是静态回显页，不能作为支付成功判据。
- 下单后购物车会清空；购物车没有删除接口，长期回归要定期清理测试账号与订单。
- 下单会占用库存，库存被打空后 fixture 会在加购阶段失败；需要在后台补库存或切换 `goods.order_item_ids`。
- 自动化新账号统一使用 `199000` 前缀（`test_data.mobile_prefix`），用于和真实账号区分、按前缀清理。

## 测试数据定期清理

每轮全量会新增约 100 个账号、30~50 笔订单，以及购物车、评价、发货单等关联数据。推荐两种做法，优先用第一种。

### 方式 A（最推荐）：专用测试库 + 快照还原

如果 TPshop 跑在独立 VM / Docker 里，测试库只服务自动化，直接整库还原最干净：

```bash
# 1. 准备基线（建库/初始化数据后执行一次）
mysqldump -h 192.168.136.132 -u tp_test -p \
  --single-transaction --routines --triggers tpshop > baseline_tpshop.sql

# 2. 回归结束后还原（或在 CI 的 teardown 里执行）
mysql -h 192.168.136.132 -u tp_test -p tpshop < baseline_tpshop.sql
```

- VM：测试前打快照，跑完回滚快照；
- Docker：`docker compose down -v` 后用 init SQL 重建，或对 MySQL volume 做快照；
- 优点：订单、库存、账号、购物车、优惠券全部回到基线，不用维护表依赖；
- 注意：**只适用于专用测试库**，共享库里有人工数据时不要整库还原。

### 方式 B（共享测试库）：按“测试前缀 + 时间”清理

项目自带 `tools/clean_test_data.py`，按测试标记清理，默认 **dry-run 不删数据**。

1. 配置数据库连接（`db.yaml` 已被 `.gitignore` 忽略）：

```bash
copy config\db.example.yaml config\db.yaml
# 编辑 host / port / user / password / database
# 本环境实际库名是 tpshop3.0，不要写成 tpshop
```

也支持环境变量：`TPSHOP_DB_HOST`、`TPSHOP_DB_PORT`、`TPSHOP_DB_USER`、`TPSHOP_DB_PASSWORD`、`TPSHOP_DB_NAME`。

2. 先看会删什么：

```bash
python tools/clean_test_data.py --days 7
```

输出会列出候选订单数、测试账号数、订单关联表、每张表将删除的行数。

3. 确认后执行（会先备份到 `backup/cleanup/<时间戳>/`）：

```bash
python tools/clean_test_data.py --execute --days 7
```

脚本的清理顺序：

```text
订单关联表（order_goods / order_action / delivery_doc / comment ...）
  → tp_order
  → 用户关联表（address / cart / comment / money_log ...）
  → tp_users
```

安全规则：

- 只处理 `mobile LIKE '199000%'` 且 `reg_time` 超过 `--days` 的账号；
- 只处理 `add_time` 超过 `--days` 的订单，不按全表时间盲删；
- `config.yaml` 里的前台主账号（`front.username`）始终跳过；
- 订单删完后仍有关联订单的用户不删；
- `--execute` 前先备份 JSONL，失败自动 rollback；
- `--limit` 控制单次处理量，避免大事务锁表；
- 默认只清理白名单表（订单、订单商品、操作日志、发货单、评价、账务日志等），不会按字段名全库乱删；发现但未自动处理的表会打印出来，确认需要可加 `--extra-order-table` / `--extra-user-table`；
- `--discover-related` 会清理所有含 `order_id`/`user_id` 的表，**危险**，仅限完全隔离的测试库使用。

脚本**不负责**：恢复库存、清理商品/SKU、删除主账号订单、清理非测试前缀的历史账号。库存建议用后台补库存或独立库基线还原。

> 历史 139 前缀账号不会被自动清理（避免误删真实用户）。首次切换时，可先用
> `SELECT DISTINCT user_id FROM tp_user_address WHERE consignee LIKE '自动化测试%'`
> 人工核对老测试账号，再写一次性清理；之后新账号统一走 `199000` 前缀即可。

### 定时执行

Windows 任务计划（每周日 02:30，路径按实际修改）：

```bat
schtasks /Create /TN "TPshopCleanTestData" ^
  /TR "\"C:\Path\python.exe\" \"E:\ruanjianceshi\Code\pythonProject5\tools\clean_test_data.py\" --execute --days 7" ^
  /SC WEEKLY /D SUN /ST 02:30 /RL HIGHEST
```

Linux cron：

```cron
0 3 * * 0 cd /opt/tpshop-test && python tools/clean_test_data.py --execute --days 7 >> logs/cleanup.log 2>&1
```

建议：清理任务失败要告警；备份保留 30 天；首次上线先连续跑一周 dry-run，核对候选范围再切 `--execute`。

> 本环境已用 `--days 0 --limit 1 --execute` 实测：成功删除 1 笔测试订单及关联行，并生成 `backup/cleanup/<时间戳>/` 下的 JSONL 备份与 `summary.json`。执行前务必先 dry-run。

## 新增用例

1. 在对应 `testcases/test_*.py` 中按现有命名加方法，用例编号写进 `pytest` 参数 id 或 Allure title；
2. 需要新状态时，在 `conftest.py` 增加 fixture，不要在用例里重复写登录/下单；
3. 新接口封装到 `api/`，不要在用例里直接拼 URL；
4. 成功响应契约加到 `utils/contracts.py`；
5. 已确认缺陷加 `@pytest.mark.xfail(reason="BUG-xx ...", strict=False)`。





