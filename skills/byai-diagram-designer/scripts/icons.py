#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
byai-diagram-designer · 图标库

全部为 24×24 视框内的扁平路径，纯自绘，不引用任何外部资源与商标素材。
产品色仅作"配色提示"，不使用任何品牌 Logo 图形。
"""

# 图标名 → (path_d, 说明)
ICONS = {
    # 通用语义
    "browser":   ("M3 4h18v14H3z M3 8h18 M6.5 6h.01 M9 6h.01", "浏览器 / 前端"),
    "server":    ("M3 5h18v6H3z M3 13h18v6H3z M7 8h.01 M7 16h.01", "服务 / 后端"),
    "database":  ("M12 3c4.4 0 8 1.1 8 2.5S16.4 8 12 8 4 6.9 4 5.5 7.6 3 12 3z "
                  "M4 5.5v13C4 19.9 7.6 21 12 21s8-1.1 8-2.5v-13 M4 12c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5", "数据库"),
    "storage":   ("M4 7h16v10H4z M4 11h16 M8 15h.01", "存储"),
    "cloud":     ("M7 18h10a3.5 3.5 0 0 0 .4-7A5 5 0 0 0 7.6 9.6A3.7 3.7 0 0 0 7 18z", "云"),
    "shield":    ("M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z M9 12l2 2 4-4", "安全 / 风控"),
    "queue":     ("M3 7h5v10H3z M10 7h5v10h-5z M17 9h4v6h-4", "消息队列"),
    "robot":     ("M6 8h12v9H6z M9 5v3 M15 5v3 M9.5 12h.01 M14.5 12h.01 "
                  "M10 14.5h4 M12 3v2 M4 11v4 M20 11v4", "Agent / 机器人"),
    "brain":     ("M12 5a3 3 0 0 0-5.6 1.5A3 3 0 0 0 6 12a3 3 0 0 0 1.6 4.6"
                  "A3 3 0 0 0 12 19z M12 5a3 3 0 0 1 5.6 1.5A3 3 0 0 1 18 12"
                  "a3 3 0 0 1-1.6 4.6A3 3 0 0 1 12 19z", "大模型 / LLM"),
    "vector":    ("M12 3l8 5v8l-8 5-8-5V8z M12 12l8-4 M12 12v8 M12 12L4 8", "向量库"),
    "user":      ("M12 4a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7z M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6", "用户"),
    "gear":      ("M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z "
                  "M12 3l1.2 2.2 2.4-.6 1 2.3 2.3 1-.6 2.4L20 12l-1.7 1.7.6 2.4-2.3 1-1 2.3-2.4-.6L12 21l-1.2-2.2-2.4.6-1-2.3-2.3-1 .6-2.4L4 12l1.7-1.7-.6-2.4 2.3-1 1-2.3 2.4.6z",
                  "处理 / 引擎"),
    "api":       ("M9 4v6a3 3 0 0 0 3 3h3 M15 4v6a3 3 0 0 1-3 3H9 "
                  "M4 8h4 M4 16h4 M16 8h4 M16 16h4", "API / 接口"),
    "cache":     ("M4 6h16v4H4z M4 14h16v4H4z M7 8h.01 M7 16h.01 M11 8h6 M11 16h6", "缓存"),
    "search":    ("M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M16.5 16.5L21 21", "检索 / 搜索"),
    "code":      ("M9 8l-4 4 4 4 M15 8l4 4-4 4", "代码"),
    "terminal":  ("M3 5h18v14H3z M7 10l2.5 2L7 14 M12.5 15h4", "终端"),
    "lock":      ("M6 11h12v9H6z M9 11V8a3 3 0 0 1 6 0v3", "鉴权 / 加密"),
    "network":   ("M12 4a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z M5 15a2.5 2.5 0 1 0 0 5"
                  " 2.5 2.5 0 0 0 0-5z M19 15a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z "
                  "M10.2 8 6.5 14.5 M13.8 8l3.7 6.5 M7.5 17.5h9", "网络 / 拓扑"),
    "container": ("M4 7l8-3 8 3-8 3z M4 7v10l8 3 8-3V7 M12 10v10", "容器 / 编排"),
    "gpu":       ("M4 8h16v8H4z M8 12h8 M4 10h16 M8 4v4 M16 4v4 M8 16v4 M16 16v4", "算力 / GPU"),
    "memory":    ("M4 8h16v8H4z M8 8v8 M12 8v8 M16 8v8", "记忆 / 存储层"),
    "planner":   ("M5 4h14v16H5z M8 8h8 M8 12h8 M8 16h5", "规划器"),
    "tool":      ("M14 4l6 6-3 3-6-6z M11 7l-7 7 3 3 7-7", "工具"),
    "doc":       ("M6 3h8l4 4v14H6z M14 3v4h4 M9 12h6 M9 16h6", "文档"),
    "chart":     ("M4 20V10 M10 20V4 M16 20v-7 M22 20H2", "指标 / 监控"),
    "bell":      ("M6 16V11a6 6 0 0 1 12 0v5l2 3H4z M10 19a2 2 0 0 0 4 0", "告警"),
    "filter":    ("M3 5h18l-7 8v6l-4 2v-8z", "过滤 / 路由"),
    "loop":      ("M5 9a7 7 0 0 1 12-2 M19 15a7 7 0 0 1-12 2 M17 3v4h-4 M7 21v-4h4", "循环 / 迭代"),
    "clock":     ("M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z M12 8v4l3 2", "定时 / 调度"),
    "spark":     ("M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z", "生成 / 推理"),
    "embed":     ("M12 3l3 6 6 1-4.5 4.2L17.5 21 12 18l-5.5 3 1-6.8L3 10l6-1z", "向量化"),
    "git":       ("M6 4v10a3 3 0 0 0 3 3h6 M18 8a3 3 0 1 0 0 6 3 3 0 0 0 0-6z "
                  "M6 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4z M18 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
                  "代码仓库"),
    "github":    ("M12 3a9 9 0 0 0-2.8 17.5c.4.1.6-.2.6-.5v-1.8c-2.6.6-3.2-1.2-3.2-1.2"
                  "-.4-1.1-1-1.4-1-1.4-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.3 1.1 2.9.8"
                  ".1-.7.4-1.1.7-1.4-2.2-.2-4.5-1.1-4.5-4.9 0-1.1.4-2 1-2.7-.1-.3-.4-1.3.1-2.6"
                  "0 0 .8-.3 2.7 1a9.3 9.3 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .5 1.3.2 2.3.1 2.6"
                  ".6.7 1 1.6 1 2.7 0 3.8-2.3 4.7-4.5 4.9.4.4.7 1 .7 2v3c0 .3.2.6.7.5"
                  "A9 9 0 0 0 12 3z", "代码托管"),
    "python":    ("M12 3c-2 0-3 1-3 2v2h6v1H8a3 3 0 0 0-3 3v3a3 3 0 0 0 3 3h2v-3a3 3 0 0 1 3-3"
                  "h5a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-3V5a3 3 0 0 0-3-2z", "Python"),
    "js":        ("M4 4h16v16H4z M10 9v5a2 2 0 0 0 3 2 M15 9c0 3-1 4-3 5", "JavaScript"),
    "react":     ("M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z "
                  "M12 6c4 1.6 6.9 3.6 8.7 6-1.8 2.4-4.7 4.4-8.7 6-4-1.6-6.9-3.6-8.7-6"
                  "C5.1 9.6 8 7.6 12 6z M6.5 15.5c2.9-2.5 6.6-2.5 11 0 "
                  "M17.5 8.5c-3 2.5-7 2.5-11 0", "React"),
    "kafka":     ("M4 6h4v12H4z M10 6h4v12h-4z M16 9h4v6h-4", "消息队列 Kafka"),
    "postgres":  ("M12 3c4 0 7 1.4 7 3s-3 3-7 3-7-1.4-7-3 3-3 7-3z "
                  "M5 6v12c0 1.6 3 3 7 3s7-1.4 7-3V6", "PostgreSQL"),
    "redis":     ("M3 8l9-4 9 4-9 4z M3 12l9 4 9-4 M3 16l9 4 9-4", "Redis"),
    "mysql":     ("M4 8c2-3 6-4 9-3s5 4 3 6-6 3-9 2 M6 14c1 3 4 5 7 5", "MySQL"),
    "mongo":     ("M12 3c3 3 5 6 5 10s-2 6-5 8c-3-2-5-4-5-8s2-7 5-10z M12 6v13", "MongoDB"),
    "elastic":   ("M5 12a7 7 0 0 1 14 0 M4 14c2 4 14 4 16 0 M6 17c2 3 10 3 12 0", "ElasticSearch"),
    "docker":    ("M4 13h13v5H4z M7 13v-2h3v2 M11 11V9h3v2 M15 11V9h3v2 M2 18c2 0 3 1 4 2", "Docker"),
    "k8s":       ("M12 3l8 4v10l-8 4-8-4V7z M12 8l4 2v4l-4 2-4-2v-4z", "Kubernetes"),
    "nginx":     ("M4 8h16v8H4z M8 8v8 M12 8v8 M16 8v8", "Nginx"),
    "grpc":      ("M5 7h14v4H5z M5 13h14v4H5z M8 9h.01 M8 15h.01", "gRPC"),
    "lambda":    ("M5 20l6-16h3l-3 8h4l-4 8z", "Serverless"),
    "bucket":    ("M5 7h14l-1.5 12h-11z M4 7h16 M10 11v4 M14 11v4", "对象存储"),
    "warehouse": ("M3 10l9-6 9 6v10H3z M8 20v-6h8v6", "数仓"),
}

# 产品配色提示（仅配色，不是商标）
BRAND_COLORS = {
    "python": "#3776AB", "js": "#F7DF1E", "react": "#61DAFB", "kafka": "#231F20",
    "postgres": "#336791", "redis": "#DC382D", "mysql": "#4479A1", "mongo": "#47A248",
    "elastic": "#FEC514", "docker": "#2496ED", "k8s": "#326CE5", "nginx": "#009639",
    "grpc": "#244C5A", "lambda": "#FF9900", "bucket": "#8C4FFF", "warehouse": "#5A6B87",
    "github": "#24292F", "git": "#F05032", "openai": "#10A37F", "anthropic": "#D97757",
}

# 节点语义类型 → 默认图标
TYPE_ICON = {
    "frontend": "browser", "backend": "server", "database": "database",
    "storage": "storage", "cloud": "cloud", "security": "shield",
    "messagebus": "queue", "external": "network", "llm": "brain", "agent": "robot",
    "vector": "vector", "user": "user", "process": "gear", "decision": "filter",
    "terminal": "terminal", "note": "doc", "default": "server",
}


def get_icon(name, ntype=None):
    if name and name in ICONS:
        return ICONS[name]
    if ntype and ntype in TYPE_ICON and TYPE_ICON[ntype] in ICONS:
        return ICONS[TYPE_ICON[ntype]]
    if ntype == "default":
        return None
    return None


def brand_color(name, fallback):
    return BRAND_COLORS.get(str(name or "").lower(), fallback)
