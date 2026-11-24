"""日界裁决（只读）。

全局唯一架构（站规.日界架构），本工程贯彻：
    架构_日界强制切开 = "日界强制切开禁跨"
跨自然日的一对进站/出站不得一笔成对：进站腿在水位越过日界时被强制结并旁路
（旁路原因=日界禁跨），其后出站按出站孤儿/新日规则落旁路。

硬约束：
- 日界是区间关系硬约束——日切或允许必须同票，全局只贯彻一种口径；
- 一切日界计算只认「事件时」（带时区），禁止用处理时/装载日代替事件日；
- 本模块不写任何库表，仅提供只读裁决，写闸在 services.配对。

两口径对「23:50 进、次日 00:10 出」必须可区分，见 口径分叉。
"""
from datetime import time, timedelta
from zoneinfo import ZoneInfo

from app.services import 时间

架构_允许跨日成对 = "允许跨日成对"
架构_日界强制切开 = "日界强制切开禁跨"

# 全局选定口径：日界强制切开禁跨
当前架构 = 架构_日界强制切开

默认时区 = "UTC"
默认日界时刻 = "00:00"

# 两口径分叉自证：同一对事件在两种架构下的命运必须不同
口径分叉 = {
    "样例": "23:50进站、次日00:10出站",
    架构_允许跨日成对: {"一笔行程": True, "是否跨日": True, "命运": "跨日成对", "valid": True},
    架构_日界强制切开: {"一笔行程": False, "是否跨日": True, "命运": "日界禁跨", "valid": False},
}


def 取站规(conn) -> dict:
    return {r["键"]: r["值"] for r in conn.execute("SELECT 键, 值 FROM 站规")}


def 当前口径(conn) -> str:
    return 取站规(conn).get("日界架构", 当前架构)


def _时区(规: dict) -> ZoneInfo:
    try:
        return ZoneInfo(规.get("站规时区", 默认时区) or 默认时区)
    except Exception:
        return ZoneInfo(默认时区)


def _日界时分(规: dict) -> time:
    try:
        时, 分 = (规.get("日界时刻", 默认日界时刻) or 默认日界时刻).split(":")
        return time(int(时), int(分))
    except Exception:
        return time(0, 0)


def 事件日(事件时: str, 规: dict) -> str:
    """事件在站规时区、按日界时刻切出的运营日（YYYY-MM-DD）。

    只用事件时：先转到站规时区，若本地钟点早于日界时刻，运营日回退一天。
    """
    本地 = 时间.解析(事件时).astimezone(_时区(规)).replace(tzinfo=None)
    if 本地.time() < _日界时分(规):
        本地 = 本地 - timedelta(days=1)
    return 本地.date().isoformat()


def 应强制结(conn, 进站事件时: str, 水位事件时: str, 规: dict | None = None) -> bool:
    """强制切开口径下，进站运营日已落后于水位运营日 → 在途腿须日界强制结。"""
    规 = 规 if 规 is not None else 取站规(conn)
    if 规.get("日界架构", 当前架构) != 架构_日界强制切开:
        return False
    return 事件日(进站事件时, 规) != 事件日(水位事件时, 规)


def 裁决(conn, 进站事件时: str, 出站事件时: str | None = None) -> dict:
    """只读日界裁决。

    返回：进站日、出站日、是否跨日、命运、valid，以及架构/时区/日界时刻与
    「一笔行程」结论。出站事件时缺省表示只裁进站腿（待出站）。
    """
    规 = 取站规(conn)
    架 = 规.get("日界架构", 当前架构)
    进站日 = 事件日(进站事件时, 规)
    出站日 = 事件日(出站事件时, 规) if 出站事件时 else ""
    跨日 = bool(出站事件时) and 进站日 != 出站日

    if not 出站事件时:
        命运, valid, 一笔 = "待出站", True, None
    elif 架 == 架构_允许跨日成对:
        命运 = "跨日成对" if 跨日 else "同日成对"
        valid, 一笔 = True, True
    else:
        if 跨日:
            命运, valid, 一笔 = "日界禁跨", False, False
        else:
            命运, valid, 一笔 = "同日成对", True, True

    return {
        "日界架构": 架,
        "站规时区": 规.get("站规时区", 默认时区),
        "日界时刻": 规.get("日界时刻", 默认日界时刻),
        "进站事件时": 进站事件时,
        "出站事件时": 出站事件时 or "",
        "进站日": 进站日,
        "出站日": 出站日,
        "是否跨日": 跨日,
        "命运": 命运,
        "valid": valid,
        "一笔行程": 一笔,
    }
