import React, { useState } from "react";
import { 取 } from "../api.js";

const 例 = [
  ["2026-11-22T23:50:00Z", "2026-11-23T00:10:00Z"],
  ["2026-11-22T08:00:00Z", "2026-11-22T09:00:00Z"],
];

export default function 日界裁决页() {
  const [进站, 设进] = useState(例[0][0]);
  const [出站, 设出] = useState(例[0][1]);
  const [果, 设果] = useState(null);
  const [讯, 设讯] = useState("");

  const 裁 = async () => {
    设讯("裁决中…");
    try {
      const q = `?进站事件时=${encodeURIComponent(进站)}&出站事件时=${encodeURIComponent(出站)}`;
      const r = await 取(`/日界裁决${q}`);
      设果(r);
      设讯("");
    } catch (e) {
      设讯(String(e.message || e));
    }
  };

  return (
    <div>
      <h1 className="题">日界裁决（只读）</h1>
      <p className="述">
        全局口径「日界强制切开禁跨」。只按<b>事件时</b>（站规时区/日界时刻）裁运营日，
        禁止用处理日代替事件日。输出进站日、出站日、是否跨日、命运、valid。
      </p>
      <div className="行" style={{ gap: "0.6rem", flexWrap: "wrap" }}>
        <label>进站事件时
          <input value={进站} onChange={(e) => 设进(e.target.value)} style={{ marginLeft: 6 }} />
        </label>
        <label>出站事件时
          <input value={出站} onChange={(e) => 设出(e.target.value)} style={{ marginLeft: 6 }} />
        </label>
        <button className="次 亮片" onClick={裁}>裁决</button>
      </div>
      <div className="行" style={{ gap: "0.5rem", marginTop: 8 }}>
        {例.map(([a, b]) => (
          <button key={a} className="次" onClick={() => { 设进(a); 设出(b); 设果(null); }}>
            {a.slice(11, 16)} → {b.slice(11, 16)}
          </button>
        ))}
      </div>
      {讯 && <p className="讯">{讯}</p>}
      {果 && (
        <table style={{ marginTop: 12, maxWidth: 720 }}>
          <tbody>
            {[
              ["日界架构", 果.日界架构],
              ["站规时区 / 日界时刻", `${果.站规时区} / ${果.日界时刻}`],
              ["进站日", 果.进站日],
              ["出站日", 果.出站日],
              ["是否跨日", 果.是否跨日 ? "是" : "否"],
              ["命运", 果.命运],
              ["valid", String(果.valid)],
              ["一笔行程", 果.一笔行程 === null ? "—" : 果.一笔行程 ? "是" : "否"],
            ].map(([k, v]) => (
              <tr key={k}>
                <td style={{ fontWeight: 600 }}>{k}</td>
                <td>
                  {k === "valid" ? (
                    <span className={`徽章 ${果.valid ? "通" : "败"}`}>{v}</span>
                  ) : v}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
