# -*- coding: utf-8 -*-
"""
繪製三種位移曲線（對應 no_shotcrete_cycle_displacement_v4.csv 的結構）
參考 D:/FLAC/0517/plot_cycle_displacement.py，但本 CSV 無 delay_cycle/mapping/ring 表，
且 cycle 記錄只在「監測步」(2608->step23, 2896->step25) 才有。

三種圖（每個監測斷面各一張，存於對應子資料夾）：
  1. full_history   : 位移 vs step_pair (0~54)，整個開挖歷程；紅線標監測步。
  2. only_history   : 監測步自身的 cycle 記錄 [50,100,200,300,400,500,1000] 的位移演化。
  3. post_history   : 監測步之後(step>=監測步)、相對監測步基準的位移（baseline 扣除）。

位移定義：
  crown        = rock_crown_<id>_z * 1000  (mm)
  convergence  = (-rock_wallL_<id>_y + rock_wallR_<id>_y) * 1000  (mm，正=內收)
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

CSV_PATH = Path(r"D:/FLAC_AI/3D_far/0601/out/no_shotcrete_cycle_displacement_v4.csv")
BASE_OUT = CSV_PATH.parent / "cycle_displacement_plots"
DIR_FULL = BASE_OUT / "full_history"
DIR_ONLY = BASE_OUT / "only_history"
DIR_POST = BASE_OUT / "post_history"
MM = 1000.0
MONITORS = [2608, 2896]
MAX_FACE_DIST = 50.0  # 開挖面距離副軸上限 (m)


def face_dist(df, mid):
    """|開挖中心 - 監測點| (m)，裁切到 MAX_FACE_DIST。2608 用 L、2896 用 R 的開挖中心。"""
    if mid == 2608:
        center = (df["L_xmin"] + df["L_xmax"]) / 2.0
    else:
        center = (df["R_xmin"] + df["R_xmax"]) / 2.0
    return (center - mid).abs().clip(upper=MAX_FACE_DIST)


def crown_mm(df, mid):
    return df["rock_crown_{0}_z".format(mid)] * MM


def conv_mm(df, mid):
    return (-df["rock_wallL_{0}_y".format(mid)] + df["rock_wallR_{0}_y".format(mid)]) * MM


def monitor_step(conv, mid):
    """開挖面首次越過該斷面的 step_pair。"""
    if mid == 2608:
        hit = conv[conv["L_xmax"] >= mid]
    else:
        hit = conv[conv["R_xmin"] <= mid]
    return int(hit["step_pair"].iloc[0]) if len(hit) else int(conv["step_pair"].iloc[0])


def nice_ylim(vmin, vmax, pad_frac=0.05):
    """加 5% padding 的 Y 範圍（含 0）。"""
    lo = min(vmin, 0.0)
    hi = max(vmax, 0.0)
    span = hi - lo
    if span <= 0:
        span = 1.0
    p = span * pad_frac
    return (lo - p, hi + p)


def plot_full(conv, mid, mstep, ylim):
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=160)
    ax.plot(conv["step_pair"], crown_mm(conv, mid), "-o", ms=3, lw=1.6, label="Crown settlement (z)")
    ax.plot(conv["step_pair"], conv_mm(conv, mid), "-s", ms=3, lw=1.6, label="Sidewall convergence (-Ly+Ry)")
    ax.axvline(mstep, color="red", lw=1.3, alpha=0.8, label="Monitor step = {0}".format(mstep))
    ax.axhline(0, color="k", lw=0.8, alpha=0.5)
    ax.set_title("full_history  monitor x={0}".format(mid))
    ax.set_xlabel("step_pair (0~54)")
    ax.set_ylabel("Displacement (mm)")
    ax.set_ylim(ylim)
    ax.grid(True, alpha=0.3)

    ax2 = ax.twinx()
    ax2.plot(conv["step_pair"], face_dist(conv, mid), color="0.35", ls=":", lw=1.5,
             drawstyle="steps-post", label="Distance from excavation face")
    ax2.set_ylabel("Distance from excavation face (m)")
    ax2.set_ylim(0, MAX_FACE_DIST)
    ax2.set_yticks([0, 10, 20, 30, 40, 50])

    l1, lab1 = ax.get_legend_handles_labels()
    l2, lab2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, lab1 + lab2, loc="best")
    fig.tight_layout()
    fig.savefig(DIR_FULL / "full_history_x{0}.png".format(mid), bbox_inches="tight")
    plt.close(fig)


def plot_only(cyc, mid, mstep, ylim):
    own = cyc[cyc["step_pair"] == mstep].sort_values("cycle")
    if own.empty:
        print("[WARN] no cycle records at step {0} for monitor {1}".format(mstep, mid))
        return
    fig, ax = plt.subplots(figsize=(8.5, 5), dpi=160)
    ax.plot(own["cycle"], crown_mm(own, mid), "-o", ms=4, lw=1.6, label="Crown settlement (z)")
    ax.plot(own["cycle"], conv_mm(own, mid), "-s", ms=4, lw=1.6, label="Sidewall convergence")
    ax.axhline(0, color="k", lw=0.8, alpha=0.5)
    ax.set_title("only_history (monitor step {0} own cycles)  x={1}".format(mstep, mid))
    ax.set_xlabel("cycle within monitor step")
    ax.set_ylabel("Displacement (mm)")
    ax.set_xticks([50, 100, 200, 300, 400, 500, 1000])
    ax.set_ylim(ylim)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(DIR_ONLY / "only_history_x{0}.png".format(mid), bbox_inches="tight")
    plt.close(fig)


def plot_post(conv, mid, mstep, ylim):
    post = conv[conv["step_pair"] >= mstep].copy().sort_values("step_pair")
    if post.empty:
        return
    base_c = crown_mm(post, mid).iloc[0]
    base_v = conv_mm(post, mid).iloc[0]
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=160)
    ax.plot(post["step_pair"], crown_mm(post, mid) - base_c, "-o", ms=3, lw=1.6,
            label="Crown (relative to monitor step)")
    ax.plot(post["step_pair"], conv_mm(post, mid) - base_v, "-s", ms=3, lw=1.6,
            label="Convergence (relative to monitor step)")
    ax.axhline(0, color="k", lw=0.9, ls="--", alpha=0.7)
    ax.set_title("post_history (after monitor step {0}, baseline-subtracted)  x={1}".format(mstep, mid))
    ax.set_xlabel("step_pair (monitor step ~ 54)")
    ax.set_ylabel("Relative displacement (mm)")
    ax.set_ylim(ylim)
    ax.grid(True, alpha=0.3)

    ax2 = ax.twinx()
    ax2.plot(post["step_pair"], face_dist(post, mid), color="0.35", ls=":", lw=1.5,
             drawstyle="steps-post", label="Distance from excavation face")
    ax2.set_ylabel("Distance from excavation face (m)")
    ax2.set_ylim(0, MAX_FACE_DIST)
    ax2.set_yticks([0, 10, 20, 30, 40, 50])

    l1, lab1 = ax.get_legend_handles_labels()
    l2, lab2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, lab1 + lab2, loc="best")
    fig.tight_layout()
    fig.savefig(DIR_POST / "post_history_x{0}.png".format(mid), bbox_inches="tight")
    plt.close(fig)


def main():
    for d in (DIR_FULL, DIR_ONLY, DIR_POST):
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.png"):
            old.unlink()

    df = pd.read_csv(CSV_PATH)
    conv = df[df["phase"].astype(str).str.startswith("conv")].copy()
    cyc = df[df["phase"].astype(str) == "cycle"].copy()

    msteps = {mid: monitor_step(conv, mid) for mid in MONITORS}

    # ---- 計算每種圖跨兩斷面的全域 Y 範圍（統一刻度）----
    full_vals, only_vals, post_vals = [], [], []
    for mid in MONITORS:
        full_vals += list(crown_mm(conv, mid)) + list(conv_mm(conv, mid))
        own = cyc[cyc["step_pair"] == msteps[mid]]
        if not own.empty:
            only_vals += list(crown_mm(own, mid)) + list(conv_mm(own, mid))
        post = conv[conv["step_pair"] >= msteps[mid]]
        if not post.empty:
            bc = crown_mm(post, mid).iloc[0]
            bv = conv_mm(post, mid).iloc[0]
            post_vals += list(crown_mm(post, mid) - bc) + list(conv_mm(post, mid) - bv)
    ylim_full = nice_ylim(min(full_vals), max(full_vals))
    ylim_only = nice_ylim(min(only_vals), max(only_vals))
    ylim_post = nice_ylim(min(post_vals), max(post_vals))
    print("ylim full={0}  only={1}  post={2}".format(
        tuple(round(v) for v in ylim_full),
        tuple(round(v) for v in ylim_only),
        tuple(round(v) for v in ylim_post)))

    for mid in MONITORS:
        mstep = msteps[mid]
        print("monitor {0}: step={1}  final crown={2:.1f}mm  final conv={3:.1f}mm".format(
            mid, mstep, crown_mm(conv, mid).iloc[-1], conv_mm(conv, mid).iloc[-1]))
        plot_full(conv, mid, mstep, ylim_full)
        plot_only(cyc, mid, mstep, ylim_only)
        plot_post(conv, mid, mstep, ylim_post)

    print("done ->", BASE_OUT)


if __name__ == "__main__":
    main()
