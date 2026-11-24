from datetime import datetime, timezone

from app.db import 连接

建表 = """
CREATE TABLE IF NOT EXISTS 站规 (
  键 TEXT PRIMARY KEY,
  值 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 线路 (
  线路键 TEXT PRIMARY KEY,
  名称 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 站点 (
  站点键 TEXT PRIMARY KEY,
  线路键 TEXT NOT NULL REFERENCES 线路(线路键),
  站名 TEXT NOT NULL,
  站序 INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS 刷卡点 (
  事件编号 TEXT PRIMARY KEY,
  卡号 TEXT NOT NULL,
  站点键 TEXT NOT NULL,
  方向 TEXT NOT NULL,
  事件时 TEXT NOT NULL,
  处理时 TEXT NOT NULL,
  命运 TEXT NOT NULL DEFAULT '已入流',
  行程键 TEXT NOT NULL DEFAULT '',
  批次编号 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 装载批次 (
  编号 TEXT PRIMARY KEY,
  时刻 TEXT NOT NULL,
  报告 TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS 开腿账 (
  开腿键 TEXT PRIMARY KEY,
  卡号 TEXT NOT NULL,
  进站事件编号 TEXT NOT NULL,
  进站站点键 TEXT NOT NULL,
  进站事件时 TEXT NOT NULL,
  状态 TEXT NOT NULL DEFAULT '在途',
  更新处理时 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 行程账 (
  行程键 TEXT PRIMARY KEY,
  卡号 TEXT NOT NULL,
  进站事件编号 TEXT NOT NULL,
  出站事件编号 TEXT NOT NULL,
  进站站点键 TEXT NOT NULL,
  出站站点键 TEXT NOT NULL,
  进站事件时 TEXT NOT NULL,
  出站事件时 TEXT NOT NULL,
  历时秒 INTEGER NOT NULL DEFAULT 0,
  进站日 TEXT NOT NULL DEFAULT '',
  出站日 TEXT NOT NULL DEFAULT '',
  是否跨日 INTEGER NOT NULL DEFAULT 0,
  日界架构 TEXT NOT NULL DEFAULT '',
  状态 TEXT NOT NULL DEFAULT '已成对',
  版本 INTEGER NOT NULL DEFAULT 1,
  处理时 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 旁路匣 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  原因 TEXT NOT NULL,
  卡号 TEXT NOT NULL DEFAULT '',
  事件编号 TEXT NOT NULL DEFAULT '',
  载荷 TEXT NOT NULL,
  时刻 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 行程贯验 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  时刻 TEXT NOT NULL,
  刷卡数 INTEGER NOT NULL,
  行程数 INTEGER NOT NULL,
  开腿数 INTEGER NOT NULL,
  旁路数 INTEGER NOT NULL,
  是否通过 INTEGER NOT NULL,
  说明 TEXT NOT NULL
);
"""


def 此刻() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _列名(conn, 表: str) -> set:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({表})")}


默认站规 = {
    "站名": "闸对",
    "最大行程秒": "7200",
    "同站进出": "允许",
    "重复进站策略": "旧腿旁路并开新腿",
    "配对策略": "同卡先进后出",
    "日界架构": "日界强制切开禁跨",
    "站规时区": "UTC",
    "日界时刻": "00:00",
    "骨架": "刷卡点装载→同卡进站出站成对物化→缺腿异向超时旁路→行程账与刷卡点互证",
}


def 迁移(conn) -> None:
    """旧库补列；建表语句只对新库生效，存量卷靠这里演进。

    站规/线路的补键放在 初始化库 里做幂等 upsert，不能在此先插键——
    否则新库会让原有的 COUNT(*)==0 整块种子被跳过。
    """
    行程列 = _列名(conn, "行程账")
    for 列, 定义 in (
        ("进站日", "TEXT NOT NULL DEFAULT ''"),
        ("出站日", "TEXT NOT NULL DEFAULT ''"),
        ("是否跨日", "INTEGER NOT NULL DEFAULT 0"),
        ("日界架构", "TEXT NOT NULL DEFAULT ''"),
    ):
        if 列 not in 行程列:
            conn.execute(f"ALTER TABLE 行程账 ADD COLUMN {列} {定义}")
    conn.commit()


def 初始化库() -> None:
    conn = 连接()
    conn.executescript(建表)
    迁移(conn)
    # 幂等补站规：新库全量播种，旧库只补缺的键，互不覆盖已有口径
    for k, v in 默认站规.items():
        conn.execute(
            "INSERT INTO 站规(键, 值) SELECT ?, ? WHERE NOT EXISTS "
            "(SELECT 1 FROM 站规 WHERE 键=?)",
            (k, v, k),
        )
    if conn.execute("SELECT COUNT(*) AS c FROM 线路").fetchone()["c"] == 0:
        conn.execute("INSERT INTO 线路(线路键, 名称) VALUES (?, ?)", ("线1", "一号线"))
        for i, (k, n) in enumerate(
            [("站A", "城东站"), ("站B", "中心站"), ("站C", "河西站")], start=1
        ):
            conn.execute(
                "INSERT INTO 站点(站点键, 线路键, 站名, 站序) VALUES (?,?,?,?)",
                (k, "线1", n, i),
            )
    conn.commit()
    conn.close()
