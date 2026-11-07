#!/usr/bin/env python3
"""复盘 Agent 破绽标注召回率计算。

前提：已完成人工标注（格式见 标注模板.csv），并导出复盘 Agent 的输出。

用法：
    python 评测/recall.py 评测/标注模板.csv agent_output.json

agent_output.json 期望格式（每场对话一条）：
[
  {
    "对话ID": "D01",
    "风险点": [
      {"轮次": 1, "红旗": "自称公检法电话办案"},
      {"轮次": 4, "红旗": "要求转账至所谓'安全账户'"}
    ]
  }
]

判定规则：
    同一对话内，人工标注的某个红旗若被 Agent 在**同一轮次**标注出来（文本包含即算命中），
    记为命中（True Positive）；否则记为漏标（False Negative）。
    Agent 标了但人工没标的记为误标（False Positive），只报告不计入召回率。

输出：
    召回率 = 命中数 / 人工标注总数
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SEP = "|"


def normalize(text: str) -> str:
    """去掉标点与空白，便于模糊比对。"""
    return "".join(ch for ch in str(text) if ch.isalnum() or "一" <= ch <= "鿿")


def load_annotation(path: Path) -> dict[str, list[dict]]:
    """读取人工标注，返回 {对话ID: [{轮次, 红旗, 原文}]}。"""
    data = defaultdict(list)
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            flags = [x.strip() for x in str(row.get("应标红旗", "")).split(SEP) if x.strip()]
            if not flags:
                continue
            data[row["对话ID"].strip()].append({
                "轮次": int(row["轮次"]),
                "红旗": flags,
                "原文": row.get("原文", "").strip(),
            })
    return dict(data)


def load_agent(path: Path) -> dict[str, list[dict]]:
    """读取 Agent 输出，返回 {对话ID: [{轮次, 红旗}]}。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    data = defaultdict(list)
    for conv in raw:
        cid = str(conv.get("对话ID", "")).strip()
        for item in conv.get("风险点", []):
            data[cid].append({
                "轮次": int(item.get("轮次", 0)),
                "红旗": str(item.get("红旗", "")),
            })
    return dict(data)


def main() -> None:
    ap = argparse.ArgumentParser(description="破绽标注召回率计算")
    ap.add_argument("annotation", help="人工标注 CSV")
    ap.add_argument("agent", help="Agent 输出 JSON")
    args = ap.parse_args()

    human = load_annotation(Path(args.annotation))
    agent = load_agent(Path(args.agent))

    total = hit = 0
    per_conv = []
    misses = []

    for cid, rows in sorted(human.items()):
        conv_total = conv_hit = 0
        agent_rows = agent.get(cid, [])
        for row in rows:
            for flag in row["红旗"]:
                conv_total += 1
                total += 1
                nflag = normalize(flag)
                matched = any(
                    a["轮次"] == row["轮次"] and nflag in normalize(a["红旗"])
                    for a in agent_rows
                )
                if matched:
                    conv_hit += 1
                    hit += 1
                else:
                    misses.append({"对话ID": cid, "轮次": row["轮次"], "漏标红旗": flag, "原文": row["原文"]})
        per_conv.append({"对话ID": cid, "标注数": conv_total, "命中": conv_hit,
                         "召回率": f"{conv_hit / conv_total:.0%}" if conv_total else "—"})

    if total == 0:
        print("人工标注里没有可用的红旗，检查 CSV 的「应标红旗」列。")
        return

    recall = hit / total
    print("=" * 52)
    print(f"人工标注红旗总数　{total}")
    print(f"Agent 命中　　　　{hit}")
    print(f"漏标　　　　　　　{total - hit}")
    print(f"召回率　　　　　　{recall:.1%}")
    target = 0.85
    print(f"目标 ≥{target:.0%}　　{'达成' if recall >= target else '未达成'}")
    print("=" * 52)

    print("\n各对话明细：")
    for r in per_conv:
        print(f"  {r['对话ID']}　标注 {r['标注数']:>2}　命中 {r['命中']:>2}　召回率 {r['召回率']}")

    if misses:
        print("\n漏标明细（前 20 条）：")
        for m in misses[:20]:
            print(f"  {m['对话ID']} 第{m['轮次']}轮　{m['漏标红旗']}")

    # 误标统计
    agent_total = sum(len(v) for v in agent.values())
    print(f"\nAgent 共标注 {agent_total} 条，其中命中 {hit} 条，其余 {agent_total - hit} 条为误标或重复。")


if __name__ == "__main__":
    main()
