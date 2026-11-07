#!/usr/bin/env python3
"""前测/后测数据分析：读取 quiz.html 导出的 CSV，算识别率提升并出图。

用法：
    python 评测/analyze.py 前测后测_全部_20条.csv
    python 评测/analyze.py *.csv --out 评测/结果

输出：
    - 控制台结论（配对提升、配对 t 检验 / Wilcoxon）
    - 结果/前测后测对比.png
    - 结果/分析报告.md
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")

# 中文字体，缺字时回退
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def load(paths: list[str]) -> pd.DataFrame:
    frames = [pd.read_csv(p, encoding="utf-8-sig") for p in paths]
    df = pd.concat(frames, ignore_index=True)
    df["阶段"] = df["阶段"].astype(str).str.strip()
    df["测试编号"] = df["测试编号"].astype(str).str.strip()
    # 同一编号同一阶段重复时保留最后一条
    df = df.drop_duplicates(subset=["测试编号", "阶段"], keep="last")
    return df


def analyze(df: pd.DataFrame) -> dict:
    pre = df[df["阶段"] == "前测"].set_index("测试编号")["得分"]
    post = df[df["阶段"] == "后测"].set_index("测试编号")["得分"]

    paired = pd.concat([pre.rename("前测"), post.rename("后测")], axis=1, join="inner").dropna()
    n = len(paired)

    result = {
        "总记录数": len(df),
        "前测人数": len(pre),
        "后测人数": len(post),
        "配对样本数": n,
    }
    if n == 0:
        result["说明"] = "没有可配对的样本（同一测试编号需同时有前测和后测）"
        return result

    pre_mean, post_mean = paired["前测"].mean(), paired["后测"].mean()
    delta = post_mean - pre_mean
    result.update({
        "前测均值": round(pre_mean, 1),
        "后测均值": round(post_mean, 1),
        "提升百分点": round(delta, 1),
        "前测识别率": f"{pre_mean:.0f}%",
        "后测识别率": f"{post_mean:.0f}%",
        "提升人数": int((paired["后测"] > paired["前测"]).sum()),
        "持平人数": int((paired["后测"] == paired["前测"]).sum()),
        "下降人数": int((paired["后测"] < paired["前测"]).sum()),
    })

    if n >= 3:
        diff = paired["后测"] - paired["前测"]
        if diff.nunique() > 1:
            t_stat, p_t = stats.ttest_rel(paired["后测"], paired["前测"])
            result["配对t检验"] = f"t={t_stat:.2f}, p={p_t:.4f}"
            if n >= 6:
                try:
                    w_stat, p_w = stats.wilcoxon(paired["后测"], paired["前测"])
                    result["Wilcoxon符号秩"] = f"W={w_stat:.1f}, p={p_w:.4f}"
                except ValueError:
                    pass
        else:
            result["检验"] = "所有样本变化量相同，无法做检验"
    else:
        result["检验"] = f"样本量 {n} < 3，只报描述统计，不做显著性检验"

    return result


def plot(paired: pd.DataFrame, out_png: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw={"width_ratios": [1, 1.4]})

    # 左：前后均值对比
    means = [paired["前测"].mean(), paired["后测"].mean()]
    bars = axes[0].bar(["前测", "后测"], means, color=["#9aa5b1", "#0a66ff"], width=0.55)
    for b, v in zip(bars, means):
        axes[0].text(b.get_x() + b.get_width()/2, v + 1.5, f"{v:.0f}", ha="center", fontsize=12, fontweight="bold")
    axes[0].set_ylim(0, 105)
    axes[0].set_ylabel("得分")
    axes[0].set_title(f"前后测均值对比（n={len(paired)}）")
    axes[0].spines[["top", "right"]].set_visible(False)

    # 右：每人连线
    for i, (_, row) in enumerate(paired.iterrows()):
        color = "#12805c" if row["后测"] > row["前测"] else ("#e5484d" if row["后测"] < row["前测"] else "#9aa5b1")
        axes[1].plot([0, 1], [row["前测"], row["后测"]], marker="o", color=color, alpha=0.65, linewidth=1.4)
    axes[1].set_xticks([0, 1])
    axes[1].set_xticklabels(["前测", "后测"])
    axes[1].set_xlim(-0.25, 1.25)
    axes[1].set_ylim(-3, 105)
    axes[1].set_ylabel("得分")
    axes[1].set_title("每名同学的变化")
    axes[1].spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="前测/后测数据分析")
    ap.add_argument("csv", nargs="+", help="quiz.html 导出的 CSV 文件")
    ap.add_argument("--out", default="评测/结果", help="输出目录")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load(args.csv)
    result = analyze(df)

    print("=" * 46)
    for k, v in result.items():
        print(f"{k:　<8}{v}")
    print("=" * 46)

    if result.get("配对样本数", 0) >= 1:
        pre = df[df["阶段"] == "前测"].set_index("测试编号")["得分"]
        post = df[df["阶段"] == "后测"].set_index("测试编号")["得分"]
        paired = pd.concat([pre.rename("前测"), post.rename("后测")], axis=1, join="inner").dropna()
        png = out_dir / "前测后测对比.png"
        plot(paired, png)
        print(f"图已保存：{png}")

    # 写 markdown 报告
    md = out_dir / "分析报告.md"
    lines = ["# 前测/后测分析报告", "", "> 由 `评测/analyze.py` 自动生成", "", "## 结果", ""]
    lines += [f"- **{k}**：{v}" for k, v in result.items()]
    lines += ["", "## 说明", "",
              "识别率 = 平均得分 / 100。提升百分点 = 后测均值 − 前测均值。",
              "配对检验要求同一测试编号同时有前测和后测记录。"]
    md.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已保存：{md}")


if __name__ == "__main__":
    main()
