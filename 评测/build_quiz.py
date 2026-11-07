#!/usr/bin/env python3
"""从 题库/前测后测-20题.md 解析题目，生成可直接双击打开的答题页 quiz.html。

单一数据源原则：题目只维护 markdown，改完题库重跑本脚本即可。

用法：
    python 评测/build_quiz.py
"""

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BANK = ROOT / "题库" / "前测后测-20题.md"
OUT = Path(__file__).resolve().parent / "quiz.html"

ANSWER_SECTION = "## 答案与解析"


def parse_questions(text: str) -> list[dict]:
    """解析题干与选项。"""
    body = text.split(ANSWER_SECTION)[0]
    # 题干形如 **1. 题目内容？**
    pattern = re.compile(
        r"\*\*(\d+)\.\s*(.+?)\*\*\s*\n((?:[A-D]\.\s*.+\n?)+)",
        re.MULTILINE,
    )
    questions = []
    for num, stem, block in pattern.findall(body):
        options = {}
        for line in block.strip().split("\n"):
            m = re.match(r"^([A-D])\.\s*(.+)$", line.strip())
            if m:
                options[m.group(1)] = m.group(2).strip()
        if len(options) != 4:
            raise ValueError(f"第 {num} 题选项不完整：{options}")
        questions.append({"id": int(num), "stem": stem.strip(), "options": options})
    return questions


def parse_answers(text: str) -> dict[int, tuple[str, str]]:
    """解析答案表，返回 {题号: (答案, 解析)}。"""
    tail = text.split(ANSWER_SECTION)[1]
    answers = {}
    for num, ans, why in re.findall(r"^\|\s*(\d+)\s*\|\s*([A-D])\s*\|\s*(.+?)\s*\|$", tail, re.MULTILINE):
        answers[int(num)] = (ans, why)
    return answers


def build() -> None:
    text = BANK.read_text(encoding="utf-8")
    questions = parse_questions(text)
    answers = parse_answers(text)

    if len(questions) != 20:
        raise ValueError(f"预期 20 题，实际解析到 {len(questions)} 题")
    missing = [q["id"] for q in questions if q["id"] not in answers]
    if missing:
        raise ValueError(f"以下题目缺答案：{missing}")

    payload = {
        "questions": questions,
        "answers": {str(k): v[0] for k, v in answers.items()},
        "explanations": {str(k): v[1] for k, v in answers.items()},
    }

    template = (Path(__file__).resolve().parent / "quiz_template.html").read_text(encoding="utf-8")
    html = template.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False, indent=2))
    OUT.write_text(html, encoding="utf-8")
    print(f"已生成 {OUT.relative_to(ROOT)}（{len(questions)} 题）")


if __name__ == "__main__":
    build()
