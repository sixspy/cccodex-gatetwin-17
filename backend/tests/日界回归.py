"""日界切开禁跨——硬推理回归（纯标准库，不依赖 fastapi/网络）。

运行：cd backend && python3 -I tests/日界回归.py
覆盖：
- 同日进出成对，行程日界字段可核；
- 跨日（23:50进/次日00:10出）强制切开：无跨日单笔，进站日界强制结+出站孤儿；
- 只读裁决接口字段（进站日/出站日/是否跨日/命运/valid）与两口径分叉；
- 禁止用处理日代替事件日；
- 日界与成对并发：同一对不得行程与旁路双落（写闸）；
- 批次末水位扫日界强制结；
- 站规时区/非零点日界；
- 贯验在日界口径下恒通过。
"""
import json
import os
import pathlib
import shutil
import sqlite3
import tempfile
import unittest

根 = pathlib.Path(__file__).resolve().parent.parent
os.environ.setdefault("夹具目录", str(根.parent / "fixtures"))


class 日界回归(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gatetwin-day-")
        os.environ["数据目录"] = self.tmp
        from app import seed
        from app.db import 库路径 as _旧路径  # noqa: F401
        import app.db as dbmod
        dbmod.库路径 = pathlib.Path(self.tmp) / "闸对.db"
        from app.services import 装载, 贯验, 日界, 配对
        self.seed = seed
        self.装载 = 装载
        self.贯验 = 贯验
        self.日界 = 日界
        self.配对 = 配对
        seed.初始化库()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _库(self):
        from app.db import 库路径
        c = sqlite3.connect(库路径)
        c.row_factory = sqlite3.Row
        return c

    def _夹具(self, 名):
        return json.loads((根.parent / "fixtures" / f"{名}.json").read_text(encoding="utf-8"))

    def _装(self, 名):
        return self.装载.装一批(self._夹具(名))

    # 夹具一：同日进出——成对
    def test_同日进出成对且日界字段可核(self):
        r = self._装("日界同日成对样例")
        self.assertEqual(r["成对"], 2)
        self.assertEqual(r["日界强制结"], 0)
        conn = self._库()
        rows = conn.execute("SELECT * FROM 行程账 ORDER BY 行程键").fetchall()
        self.assertEqual(len(rows), 2)
        for t in rows:
            self.assertEqual(t["进站日"], "2026-11-22")
            self.assertEqual(t["出站日"], "2026-11-22")
            self.assertEqual(t["是否跨日"], 0)
            self.assertEqual(t["日界架构"], "日界强制切开禁跨")
        卡91 = conn.execute(
            "SELECT * FROM 刷卡点 WHERE 事件编号 IN ('d1','d2') ORDER BY 事件编号"
        ).fetchall()
        self.assertTrue(all(x["命运"] == "已成对" for x in 卡91))
        conn.close()
        self.assertTrue(self.贯验.跑贯验()["是否通过"])

    # 夹具二甲：跨日进出——无跨日单笔（旁路或拆）；同批同日对仍成对
    def test_跨日强制切开无单笔(self):
        r = self._装("日界跨日切开样例")
        # 卡94(x3/x4)同日 → 1 笔；卡93(x1/x2)跨日 → 0 笔
        self.assertEqual(r["成对"], 1)
        self.assertEqual(r["日界强制结"], 1)  # 卡93 的进站腿
        conn = self._库()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM 行程账").fetchone()[0], 1)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM 行程账 WHERE 是否跨日=1").fetchone()[0], 0
        )
        t = conn.execute("SELECT * FROM 行程账").fetchone()
        self.assertEqual(t["进站事件编号"], "x3")
        self.assertEqual(t["出站事件编号"], "x4")
        腿 = conn.execute(
            "SELECT * FROM 开腿账 WHERE 进站事件编号='x1'"
        ).fetchone()
        self.assertEqual(腿["状态"], "日界强制结")
        原因 = {
            x["事件编号"]: x["原因"]
            for x in conn.execute("SELECT 事件编号, 原因 FROM 旁路匣")
        }
        self.assertEqual(原因["x1"], "日界禁跨")
        self.assertEqual(原因["x2"], "出站孤儿")
        命运 = {
            x["事件编号"]: x["命运"]
            for x in conn.execute("SELECT 事件编号, 命运 FROM 刷卡点")
        }
        self.assertEqual(命运["x1"], "已旁路")
        self.assertEqual(命运["x2"], "已旁路")
        # 卡94 同日（11-23）进出仍正常成对
        self.assertEqual(命运["x3"], "已成对")
        self.assertEqual(命运["x4"], "已成对")
        conn.close()
        self.assertTrue(self.贯验.跑贯验()["是否通过"])

    # 只读裁决接口：字段齐全，23:50/00:10 两口径可区分
    def test_只读裁决接口与口径分叉(self):
        conn = self._库()
        裁 = self.日界.裁决(
            conn, "2026-11-22T23:50:00Z", "2026-11-23T00:10:00Z"
        )
        self.assertEqual(裁["进站日"], "2026-11-22")
        self.assertEqual(裁["出站日"], "2026-11-23")
        self.assertTrue(裁["是否跨日"])
        self.assertFalse(裁["valid"])
        self.assertEqual(裁["命运"], "日界禁跨")
        self.assertFalse(裁["一笔行程"])
        self.assertEqual(裁["日界架构"], "日界强制切开禁跨")

        同日 = self.日界.裁决(conn, "2026-11-22T08:00:00Z", "2026-11-22T09:00:00Z")
        self.assertTrue(同日["valid"])
        self.assertEqual(同日["命运"], "同日成对")
        self.assertTrue(同日["一笔行程"])

        分叉 = self.日界.口径分叉
        self.assertTrue(分叉[self.日界.架构_允许跨日成对]["一笔行程"])
        self.assertFalse(分叉[self.日界.架构_日界强制切开]["一笔行程"])
        conn.close()

    # 硬约束：禁止用处理日代替事件日
    def test_只认事件日不认处理日(self):
        # 事件同日(11-22)，处理时全部落在次日(11-23)——仍须成对
        r = self._装("日界同日成对样例")
        self.assertEqual(r["成对"], 2)
        conn = self._库()
        t = conn.execute("SELECT * FROM 行程账 WHERE 进站事件编号='d1'").fetchone()
        self.assertEqual(t["进站日"], "2026-11-22")
        self.assertEqual(t["是否跨日"], 0)
        conn.close()

        # 事件跨日、但处理时同批同分钟——仍须切开（只数本批 c1/c3，不混上一夹具）
        r2 = self._装("日界并发双落样例")
        self.assertEqual(r2["成对"], 0)
        conn = self._库()
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM 行程账 WHERE 进站事件编号 IN ('c1','c3')"
            ).fetchone()[0],
            0,
        )
        conn.close()

    # 夹具三：日界与成对并发——不得行程与旁路双落同一对
    def test_并发不得双落(self):
        r = self._装("日界并发双落样例")
        self.assertEqual(r["成对"], 0)
        self.assertEqual(r["日界强制结"], 2)
        conn = self._库()
        # 没有任何行程
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM 行程账").fetchone()[0], 0)
        # 每个进站事件编号在旁路匣恰一条日界禁跨
        for ev in ("c1", "c3"):
            n = conn.execute(
                "SELECT COUNT(*) FROM 旁路匣 WHERE 原因='日界禁跨' AND 事件编号=?",
                (ev,),
            ).fetchone()[0]
            self.assertEqual(n, 1, f"{ev} 日界禁跨旁路应恰一条")
            双 = conn.execute(
                "SELECT COUNT(*) FROM 行程账 WHERE 进站事件编号=?", (ev,)
            ).fetchone()[0]
            self.assertEqual(双, 0, f"{ev} 不得同时有行程")
        # 每个出站事件编号恰一条孤儿旁路
        for ev in ("c2", "c4"):
            n = conn.execute(
                "SELECT COUNT(*) FROM 旁路匣 WHERE 原因='出站孤儿' AND 事件编号=?",
                (ev,),
            ).fetchone()[0]
            self.assertEqual(n, 1)
        # 开腿终态唯一
        states = [
            x["状态"]
            for x in conn.execute("SELECT 状态 FROM 开腿账")
        ]
        self.assertEqual(sorted(states), ["日界强制结", "日界强制结"])
        conn.close()
        self.assertTrue(self.贯验.跑贯验()["是否通过"])

    # 写闸：状态翻转只落一次，旁路后再成对必须失败
    def test_成对写闸拒绝双写(self):
        from app.db import 连接
        self._装("日界跨日切开样例")
        conn = 连接()
        leg = conn.execute(
            "SELECT * FROM 开腿账 WHERE 进站事件编号='x1'"
        ).fetchone()
        # 已日界强制结：再次翻转/成对都必须 0 行或抛错
        self.assertEqual(
            self.配对._状态翻转(conn, leg["开腿键"], "在途", "已成对", "2026-11-23T01:00:00Z"),
            0,
        )
        with self.assertRaises(RuntimeError):
            self.配对.成对写出站(
                conn, leg, "x2", "站B", "2026-11-23T00:10:00Z", "2026-11-23T01:00:00Z"
            )
        conn.rollback()
        conn.close()

    # 批次末水位扫日界强制结（进站无出站、水位已跨日）
    def test_水位扫日界强制结(self):
        体 = {
            "批次编号": "批-水位日界",
            "事件": [
                {"事件编号": "w1", "卡号": "卡97", "站点键": "站A", "方向": "进站",
                 "事件时": "2026-11-22T23:50:00Z", "处理时": "2026-11-22T23:50:01Z"},
                {"事件编号": "w2", "卡号": "卡98", "站点键": "站C", "方向": "出站",
                 "事件时": "2026-11-23T00:30:00Z", "处理时": "2026-11-23T00:30:01Z"},
            ],
        }
        r = self.装载.装一批(体)
        conn = self._库()
        leg = conn.execute("SELECT * FROM 开腿账 WHERE 进站事件编号='w1'").fetchone()
        self.assertEqual(leg["状态"], "日界强制结")
        self.assertEqual(r["日界强制结"], 1)
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM 旁路匣 WHERE 原因='日界禁跨' AND 事件编号='w1'"
            ).fetchone()[0],
            1,
        )
        # w2 是无腿出站 → 孤儿
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM 旁路匣 WHERE 原因='出站孤儿' AND 事件编号='w2'"
            ).fetchone()[0],
            1,
        )
        conn.close()
        self.assertTrue(self.贯验.跑贯验()["是否通过"])

    # 站规时区/非零点日界参与裁决
    def test_站规时区与日界时刻(self):
        from app.db import 连接
        conn = 连接()
        conn.execute("UPDATE 站规 SET 值='Asia/Shanghai' WHERE 键='站规时区'")
        conn.commit()
        规 = self.日界.取站规(conn)
        # UTC 23:30 = 北京次日 07:30 → 北京运营日是次日
        self.assertEqual(
            self.日界.事件日("2026-11-22T23:30:00Z", 规), "2026-11-23"
        )
        conn.execute("UPDATE 站规 SET 值='02:00' WHERE 键='日界时刻'")
        conn.commit()
        规 = self.日界.取站规(conn)
        # 北京 01:30（UTC 17:30）早于 02:00 日界 → 运营日回退一天
        self.assertEqual(
            self.日界.事件日("2026-11-22T17:30:00Z", 规), "2026-11-22"
        )
        # 北京 03:00（UTC 19:00）过 02:00 日界 → 当日
        self.assertEqual(
            self.日界.事件日("2026-11-22T19:00:00Z", 规), "2026-11-23"
        )
        conn.close()

    # 既有 happy path 不回归
    def test_既有夹具全链路不回归(self):
        self.assertEqual(self._装("成对样例")["成对"], 2)
        self.assertEqual(self._装("出站孤儿样例")["旁路"], 1)
        r = self._装("重复进站样例")
        self.assertEqual(r["旁路"], 1)
        self.assertEqual(r["成对"], 1)
        self._装("缺腿超时样例")
        self.assertTrue(self.贯验.跑贯验()["是否通过"])

    # 新库播种必须完整（迁移不得让 COUNT==0 整块种子被跳过），且二次初始化幂等
    def test_新库播种完整且幂等(self):
        conn = self._库()
        键 = {r[0] for r in conn.execute("SELECT 键 FROM 站规")}
        for 必备 in ("最大行程秒", "同站进出", "配对策略", "日界架构", "站规时区", "日界时刻", "骨架"):
            self.assertIn(必备, 键)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM 站点").fetchone()[0], 3)
        conn.close()
        self.seed.初始化库()  # 再跑一次不得报错或重复
        conn = self._库()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM 站规").fetchone()[0], len(键))
        conn.close()

    # 旧库迁移：补列补键但不覆盖既有口径
    def test_旧库迁移补列补键不覆盖(self):
        conn = self._库()
        conn.execute("UPDATE 站规 SET 值='13' WHERE 键='最大行程秒'")
        conn.commit()
        conn.close()
        self.seed.初始化库()
        conn = self._库()
        self.assertEqual(
            conn.execute("SELECT 值 FROM 站规 WHERE 键='最大行程秒'").fetchone()[0], "13"
        )
        列 = {r[1] for r in conn.execute("PRAGMA table_info(行程账)")}
        for c in ("进站日", "出站日", "是否跨日", "日界架构"):
            self.assertIn(c, 列)
        conn.close()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(根))
    unittest.main(verbosity=2)
