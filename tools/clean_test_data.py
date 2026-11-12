#!/usr/bin/env python
"""TPshop 自动化测试数据清理工具（默认 dry-run，不会删数据）。

清理范围：
1. 测试账号：mobile 以 test_data.mobile_prefix（默认 199000）开头，且 reg_time 早于 N 天；
2. 这些账号名下的订单：order.add_time 早于 N 天，且 user 为测试账号或收货人带“自动化测试”标记；
3. 订单关联表：按白名单清理 order_goods/order_action/delivery_doc/comment/account_log...；
4. 用户关联表：按白名单清理 address/cart/comment/money_log...，最后删 tp_users。
   白名单外的关联表会打印出来，需要时用 --extra-order-table / --extra-user-table 补充；
   --discover-related 可清理全部含 order_id/user_id 的表，但风险高，仅限完全隔离的库。

安全设计：
- 默认 dry-run，只统计不删除；
- --execute 才真正删除，且先备份为 JSONL；
- 只处理“测试前缀账号 + 超过 N 天”的数据，不按全表时间盲删；
- 主账号（config.yaml front.username）始终跳过；
- 有未清理订单的用户不会被删除。

用法：
    # 1. 先看将删什么
    python tools/clean_test_data.py --days 7

    # 2. 确认后执行（会备份到 backup/cleanup/<时间戳>/）
    python tools/clean_test_data.py --execute --days 7

数据库配置优先级：命令行 > 环境变量 > config/db.yaml > 默认值。
环境变量：TPSHOP_DB_HOST / TPSHOP_DB_PORT / TPSHOP_DB_USER /
          TPSHOP_DB_PASSWORD / TPSHOP_DB_NAME
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB_CONFIG = ROOT / "config" / "db.yaml"
APP_CONFIG = ROOT / "config" / "config.yaml"

ORDER_TABLE = "tp_order"
USER_TABLE = "tp_users"

# 只删明确属于订单/用户生命周期的表；不按“字段名相同”全库乱删，
# 避免 tp_shop_order / tp_shop / tp_suppliers 这类同名字段被误伤。
KNOWN_ORDER_TABLES = [
    "tp_order_goods",
    "tp_order_action",
    "tp_delivery_doc",
    "tp_comment",
    "tp_account_log",
    "tp_message_logistics",
    "tp_return_goods",
    "tp_invoice",
    "tp_order_bespeak",
    "tp_vr_order_code",
    "tp_prom_order",
    "tp_team_found",
    "tp_team_follow",
    "tp_team_lottery",
    "tp_recharge",
]
KNOWN_USER_TABLES = [
    "tp_user_address",
    "tp_cart",
    "tp_comment",
    "tp_user_login",
    "tp_user_message",
    "tp_user_sign",
    "tp_user_collection",
    "tp_goods_collect",
    "tp_goods_visit",
    "tp_account_log",
    "tp_coupon_list",
    "tp_recharge",
    "tp_user_distribution",
    "tp_user_extend",
    "tp_user_store",
    "tp_feedback",
    "tp_withdrawals",
    "tp_invoice",
    "tp_return_goods",
    "tp_message",
]


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message):
    print(f"[{now_text()}] {message}", flush=True)


def qi(identifier):
    """反引号包裹标识符，防止表名/字段名拼接注入。"""
    return "`" + str(identifier).replace("`", "``") + "`"


def placeholders(values):
    return ",".join(["%s"] * len(values))


def chunks(values, size=500):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def load_app_config():
    if not APP_CONFIG.exists():
        return {}
    with open(APP_CONFIG, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_db_config(args):
    config = {}
    if DB_CONFIG.exists():
        with open(DB_CONFIG, "r", encoding="utf-8") as file:
            config.update(yaml.safe_load(file) or {})

    env_map = {
        "host": "TPSHOP_DB_HOST",
        "port": "TPSHOP_DB_PORT",
        "user": "TPSHOP_DB_USER",
        "password": "TPSHOP_DB_PASSWORD",
        "database": "TPSHOP_DB_NAME",
    }
    for key, env_name in env_map.items():
        if os.getenv(env_name):
            config[key] = os.getenv(env_name)

    for key in ("host", "port", "user", "password", "database"):
        value = getattr(args, key, None)
        if value is not None:
            config[key] = value

    config.setdefault("host", "127.0.0.1")
    config.setdefault("port", 3306)
    config.setdefault("user", "root")
    config.setdefault("password", "")
    config.setdefault("database", "tpshop")
    config.setdefault("charset", "utf8mb4")
    config["port"] = int(config["port"])
    return config


def connect(config):
    try:
        import pymysql
    except ImportError:
        raise SystemExit(
            "缺少 pymysql，请先执行：pip install pymysql\n"
            "（该依赖只用于测试数据清理工具，不影响 pytest 用例运行）"
        )
    import pymysql
    from pymysql.cursors import DictCursor

    return pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
        charset=config["charset"],
        cursorclass=DictCursor,
        autocommit=False,
    )


def backup_rows(cursor, table, column, ids, backup_dir, prefix):
    if not ids:
        return 0
    path = backup_dir / f"{prefix}__{table}.jsonl"
    count = 0
    with open(path, "w", encoding="utf-8") as file:
        for part in chunks(ids):
            cursor.execute(
                f"SELECT * FROM {qi(table)} WHERE {qi(column)} IN ({placeholders(part)})",
                part,
            )
            for row in cursor.fetchall():
                file.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                count += 1
    return count


def columns(cursor, table):
    db = cursor.connection.db
    if isinstance(db, bytes):
        db = db.decode()
    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
        """,
        (db, table),
    )
    return {row["COLUMN_NAME"] for row in cursor.fetchall()}


def related_tables(cursor, column, exclude):
    db = cursor.connection.db
    if isinstance(db, bytes):
        db = db.decode()
    cursor.execute(
        """
        SELECT c.TABLE_NAME AS table_name
        FROM information_schema.COLUMNS c
        JOIN information_schema.TABLES t
          ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
        WHERE c.TABLE_SCHEMA = %s
          AND c.COLUMN_NAME = %s
          AND t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY c.TABLE_NAME
        """,
        (db, column),
    )
    names = [row["table_name"] for row in cursor.fetchall()]
    return [name for name in names if name not in exclude]


def resolve_tables(discovered, known, extras, use_all):
    """从发现到的表里选白名单；use_all=True 时才使用全部（风险自负）。"""
    if use_all:
        selected = list(discovered)
    else:
        selected = [name for name in known if name in discovered]
        selected += [name for name in extras if name in discovered and name not in selected]
    skipped = [name for name in discovered if name not in selected]
    return selected, skipped


def select_orders(cursor, cutoff, mobile_like, consignee_like, limit):
    order_columns = columns(cursor, ORDER_TABLE)
    params = [cutoff]
    if "consignee" in order_columns:
        where = "o.add_time < %s AND (u.mobile LIKE %s OR o.consignee LIKE %s)"
        params.extend([mobile_like, consignee_like])
    else:
        where = "o.add_time < %s AND u.mobile LIKE %s"
        params.append(mobile_like)
    params.append(limit)
    sql = f"""
        SELECT o.order_id, o.order_sn, o.user_id
        FROM {qi(ORDER_TABLE)} o
        JOIN {qi(USER_TABLE)} u ON u.user_id = o.user_id
        WHERE {where}
        ORDER BY o.order_id
        LIMIT %s
    """
    cursor.execute(sql, params)
    return cursor.fetchall()


def select_users(cursor, cutoff, mobile_like, limit, keep_mobiles):
    cursor.execute(
        f"""
        SELECT user_id, mobile
        FROM {qi(USER_TABLE)}
        WHERE mobile LIKE %s AND reg_time < %s
        ORDER BY user_id
        LIMIT %s
        """,
        (mobile_like, cutoff, limit),
    )
    return [row for row in cursor.fetchall() if row["mobile"] not in keep_mobiles]


def users_with_remaining_orders(cursor, user_ids):
    if not user_ids:
        return set()
    remaining = set()
    for part in chunks(user_ids):
        cursor.execute(
            f"SELECT DISTINCT user_id FROM {qi(ORDER_TABLE)} WHERE user_id IN ({placeholders(part)})",
            part,
        )
        remaining.update(row["user_id"] for row in cursor.fetchall())
    return remaining


def delete_by_ids(cursor, table, column, ids):
    if not ids:
        return 0
    deleted = 0
    for part in chunks(ids):
        cursor.execute(
            f"DELETE FROM {qi(table)} WHERE {qi(column)} IN ({placeholders(part)})",
            part,
        )
        deleted += cursor.rowcount
    return deleted


def main():
    parser = argparse.ArgumentParser(
        description="TPshop 测试数据清理（默认 dry-run，--execute 才删除）"
    )
    parser.add_argument("--execute", action="store_true", help="真正执行删除；不加则只统计")
    parser.add_argument("--days", type=int, default=7, help="只清理 N 天以前的数据，默认 7")
    parser.add_argument("--limit", type=int, default=500, help="单次最多处理订单数/用户数，默认 500")
    parser.add_argument("--prefix", default=None, help="测试手机号前缀，默认读 config test_data.mobile_prefix")
    parser.add_argument("--consignee-prefix", default="自动化测试", help="测试收货人前缀标记")
    parser.add_argument("--backup-dir", default=str(ROOT / "backup" / "cleanup"), help="备份目录")
    parser.add_argument("--no-users", action="store_true", help="只清订单，不删测试账号")
    parser.add_argument("--keep-mobile", action="append", default=[], help="额外保留的手机号，可重复")
    parser.add_argument("--extra-order-table", action="append", default=[], help="额外清理的订单关联表，可重复")
    parser.add_argument("--extra-user-table", action="append", default=[], help="额外清理的用户关联表，可重复")
    parser.add_argument(
        "--discover-related",
        action="store_true",
        help="危险：自动清理所有含 order_id/user_id 的表（默认只用白名单）",
    )
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--database", default=None)
    args = parser.parse_args()

    app_config = load_app_config()
    prefix = args.prefix or str(
        (app_config.get("test_data") or {}).get("mobile_prefix", "199000")
    )
    keep_mobiles = set(args.keep_mobile)
    main_mobile = str((app_config.get("front") or {}).get("username", ""))
    if main_mobile:
        keep_mobiles.add(main_mobile)

    db_config = load_db_config(args)
    cutoff = int(time.time()) - args.days * 86400
    mobile_like = f"{prefix}%"
    consignee_like = f"{args.consignee_prefix}%"

    log(
        f"数据库 {db_config['user']}@{db_config['host']}:{db_config['port']}/"
        f"{db_config['database']}，清理 {args.days} 天前数据，手机号前缀 {prefix}，"
        f"模式={'EXECUTE' if args.execute else 'DRY-RUN'}"
    )

    try:
        connection = connect(db_config)
    except Exception as exc:
        raise SystemExit(
            f"数据库连接失败：{exc}\n"
            "请检查 config/db.yaml（或 TPSHOP_DB_* 环境变量 / 命令行参数）是否正确，"
            "并确认数据库允许从本机访问。"
        )
    try:
        with connection.cursor() as cursor:
            orders = select_orders(cursor, cutoff, mobile_like, consignee_like, args.limit)
            order_ids = [row["order_id"] for row in orders]
            test_users = (
                []
                if args.no_users
                else select_users(cursor, cutoff, mobile_like, args.limit, keep_mobiles)
            )
            user_ids = [row["user_id"] for row in test_users]

            log(f"候选订单：{len(order_ids)} 笔；候选测试账号：{len(user_ids)} 个")
            if order_ids:
                log(f"订单 ID 范围：{min(order_ids)} ~ {max(order_ids)}")

            order_discovered = related_tables(cursor, "order_id", {ORDER_TABLE})
            user_discovered = related_tables(cursor, "user_id", {ORDER_TABLE, USER_TABLE})
            order_child_tables, skipped_order = resolve_tables(
                order_discovered,
                KNOWN_ORDER_TABLES,
                args.extra_order_table,
                args.discover_related,
            )
            user_child_tables, skipped_user = resolve_tables(
                user_discovered,
                KNOWN_USER_TABLES,
                args.extra_user_table,
                args.discover_related,
            )
            log("订单关联表：" + (", ".join(order_child_tables) or "无"))
            log("用户关联表：" + (", ".join(user_child_tables) or "无"))
            if skipped_order:
                log(
                    "未自动处理的订单相关表（确认需要可加 --extra-order-table）："
                    + ", ".join(skipped_order)
                )
            if skipped_user:
                log(
                    "未自动处理的用户相关表（确认需要可加 --extra-user-table）："
                    + ", ".join(skipped_user)
                )

            if not args.execute:
                for table in order_child_tables:
                    if order_ids:
                        cursor.execute(
                            f"SELECT COUNT(*) AS cnt FROM {qi(table)} "
                            f"WHERE order_id IN ({placeholders(order_ids)})",
                            order_ids,
                        )
                        log(f"  将清理 {table}: {cursor.fetchone()['cnt']} 行")
                for table in user_child_tables:
                    if user_ids:
                        cursor.execute(
                            f"SELECT COUNT(*) AS cnt FROM {qi(table)} "
                            f"WHERE user_id IN ({placeholders(user_ids)})",
                            user_ids,
                        )
                        log(f"  将清理 {table}（按用户）: {cursor.fetchone()['cnt']} 行")
                log("DRY-RUN：未删除任何数据。确认无误后加 --execute 执行。")
                return

            if not order_ids and not user_ids:
                log("没有需要清理的数据。")
                return

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = Path(args.backup_dir) / stamp
            backup_dir.mkdir(parents=True, exist_ok=True)
            log(f"备份目录：{backup_dir}")

            # 1) 备份订单 + 订单子表
            dumped = {}
            if order_ids:
                dumped[f"order__{ORDER_TABLE}.jsonl"] = backup_rows(
                    cursor, ORDER_TABLE, "order_id", order_ids, backup_dir, "order"
                )
                for table in order_child_tables:
                    dumped[f"order__{table}.jsonl"] = backup_rows(
                        cursor, table, "order_id", order_ids, backup_dir, "order"
                    )

            # 2) 先用订单子表 → 订单；再处理用户，避免半删状态
            deleted = {}
            for table in order_child_tables:
                deleted[table] = delete_by_ids(cursor, table, "order_id", order_ids)
            deleted[ORDER_TABLE] = delete_by_ids(cursor, ORDER_TABLE, "order_id", order_ids)

            # 3) 删除订单后，重新过滤“仍有订单”的用户
            remaining = users_with_remaining_orders(cursor, user_ids)
            removable_users = [uid for uid in user_ids if uid not in remaining]
            keep_count = len(user_ids) - len(removable_users)
            log(f"测试账号可删除 {len(removable_users)} 个，保留（仍有订单）{keep_count} 个")

            if removable_users:
                for table in user_child_tables:
                    dumped[f"user__{table}.jsonl"] = backup_rows(
                        cursor, table, "user_id", removable_users, backup_dir, "user"
                    )
                dumped[f"user__{USER_TABLE}.jsonl"] = backup_rows(
                    cursor, USER_TABLE, "user_id", removable_users, backup_dir, "user"
                )
                for table in user_child_tables:
                    deleted[table] = deleted.get(table, 0) + delete_by_ids(
                        cursor, table, "user_id", removable_users
                    )
                deleted[USER_TABLE] = delete_by_ids(
                    cursor, USER_TABLE, "user_id", removable_users
                )

            connection.commit()

            summary = {
                "time": now_text(),
                "days": args.days,
                "prefix": prefix,
                "orders": len(order_ids),
                "users": len(removable_users),
                "deleted_rows": deleted,
                "backup_rows": dumped,
            }
            with open(backup_dir / "summary.json", "w", encoding="utf-8") as file:
                json.dump(summary, file, ensure_ascii=False, indent=2)

            for table, count in deleted.items():
                log(f"  {table}: 删除 {count} 行")
            log(
                f"完成：订单 {len(order_ids)} 笔，测试账号 {len(removable_users)} 个；"
                f"备份与 summary 见 {backup_dir}"
            )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

