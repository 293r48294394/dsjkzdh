"""接口响应契约（Schema）。

TPshop 返回 status/msg/result 三段式；这里固化成功响应的结构，
用于“接口契约与响应结构校验”类回归（字段名/类型/必填/格式）。
"""

REGISTER_SUCCESS = {
    "type": "object",
    "required": ["status", "msg", "result"],
    "properties": {
        "status": {"type": "integer", "enum": [1]},
        "msg": {"type": "string"},
        "result": {
            "type": "object",
            "required": ["user_id", "mobile"],
            "properties": {
                "user_id": {"type": "integer", "minimum": 1},
                "mobile": {"type": "string", "pattern": r"^1\d{10}$"},
            },
        },
    },
}

LOGIN_SUCCESS = {
    "type": "object",
    "required": ["status", "msg", "result"],
    "properties": {
        "status": {"type": "integer", "enum": [1]},
        "msg": {"type": "string"},
        "result": {
            "type": "object",
            "required": ["user_id", "mobile"],
            "properties": {
                "user_id": {"type": "integer", "minimum": 1},
                "mobile": {"type": "string", "pattern": r"^1\d{10}$"},
            },
        },
    },
}

VERIFY_IMAGE = {
    "type": "object",
    "required": ["status", "msg"],
    "properties": {"status": {"type": "integer"}, "msg": {"type": "string"}},
}

CART_ADD_SUCCESS = {
    "type": "object",
    "required": ["status", "msg"],
    "properties": {
        "status": {"type": "integer", "enum": [1]},
        "msg": {"type": "string", "pattern": "加入购物车成功"},
    },
}

SUBMIT_ORDER_SUCCESS = {
    "type": "object",
    "required": ["status", "msg", "result"],
    "properties": {
        "status": {"type": "integer", "enum": [1]},
        "msg": {"type": "string", "pattern": "提交订单成功"},
        "result": {"type": "string", "pattern": r"^\d{14,20}$"},
    },
}

ADMIN_LOGIN_SUCCESS = {
    "type": "object",
    "required": ["status", "url"],
    "properties": {
        "status": {"type": "integer", "enum": [1]},
        "url": {"type": "string", "pattern": r"Admin/Index/index"},
    },
}

ADMIN_ACTION_SUCCESS = {
    "type": "object",
    "required": ["status", "msg", "url"],
    "properties": {
        "status": {"type": "integer", "enum": [1]},
        "msg": {"type": "string", "pattern": "操作成功"},
        "url": {"type": "string", "pattern": r"Order/detail"},
    },
}

COMMENT_SUCCESS = {
    "type": "object",
    "required": ["status", "msg"],
    "properties": {
        "status": {"type": "integer", "enum": [1]},
        "msg": {"type": "string", "pattern": "评论成功"},
    },
}
