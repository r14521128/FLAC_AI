# -*- coding: utf-8 -*-
"""
0603 supported run -- cycle displacement plots (3 folders x 2 monitors).
Adapted from 0601/plot_cycle_displacement_v4.py for the 0603 monitor CSV
column names (excav_monitor.csv):
  step, phase, Lxa, Lxb, Rxa, Rxb, fine, cycle, ratio_avg, ...,
  crown2608_z, conv2608, crown2896_z, conv2896, n_lined
  (crown*_z and conv* are already in metres; conv = -wallL_y + wallR_y)

Three plot types (each monitor section -> one png in its subfolder):
  1. full_history : displacement vs step (0~54), whole excavation; red line = monitor step.
  2. only_history : the monitor step's own cycle records [50..1000].
  3. post_history : after the monitor step, baseline-subtracted relative displacement.

Bonus: full_history overlays the FINAL field crown settlement (H1) as a dashed
reference line, read from data/monitoring/monitoring_data.csv.

Run:  python plot_cycle_displacement_0603.py
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

CSV_PATH = Path(r"D:/FLAC_AI/3D_far/0603/out/excav_monitor.csv")
FIELD_CSV = Path(r"D:/FLAC_AI/data/monitoring/monitoring_data.csv")
BASE_OUT = CSV_PATH.parent / "cycle_displacement_plots"
DIR_FULL = BASE_OUT / "full_history"
DIR_ONLY = BASE_OUT / "only_history"
DIR_POST = BASE_OUT / "post_history"
MM = 1000.0
MONITORS = [2608, 2896]
MAX_FACE_DIST = 50.0  # distance-from-face secondary axis cap (m)
FACE_PAST = 4.0       # post_history datum: face advanced this many m PAST the section
FINE_HALF = 36.0      # fine-step half-zone; post_history stops once the face is this far past
POST_YLIM = (-120.0, 0.0)  # fixed y-axis for post_history
SHOW_FIELD = False    # monitoring_data.csv is NOT real field data yet -> no field overlay


def face_dist(df, mid):
    """|excavation centre - monitor| (m), clipped. 2608 uses L, 2896 uses R."""
    if mid == 2608:
        center = (df["Lxa"] + df["Lxb"]) / 2.0
    else:
        center = (df["Rxa"] + df["Rxb"]) / 2.0
    return (center - mid).abs().clip(upper=MAX_FACE_DIST)


def crown_mm(df, mid):
    return df["crown{0}_z".format(mid)] * MM


def conv_mm(df, mid):
    # 0603 CSV already stores conv = -wallL_y + wallR_y (metres)
    return df["conv{0}".format(mid)] * MM


def monitor_step(conv, mid):
    """step at which the excavation face first crosses the section."""
    if mid == 2608:
        hit = conv[conv["Lxb"] >= mid]
    else:
        hit = conv[(conv["Rxa"] <= mid) & (conv["Rxa"] > 0)]
    return int(hit["step"].iloc[0]) if len(hit) else int(conv["step"].iloc[0])


def datum_step(conv, mid, past=FACE_PAST):
    """step at which the excavation face (leading edge) has advanced `past`
    metres BEYOND the section. Used as the post_history zero datum, mimicking
    a field instrument installed `past` m behind the face.
    2608 advances +x (leading edge = Lxb); 2896 advances -x (leading edge = Rxa)."""
    if mid == 2608:
        hit = conv[conv["Lxb"] >= mid + past]
    else:
        hit = conv[(conv["Rxa"] <= mid - past) & (conv["Rxa"] > 0)]
    if len(hit):
        return int(hit["step"].iloc[0])
    return monitor_step(conv, mid)


def field_final_crown(mid):
    """final (last step_pair) field crown settlement H1 (mm) at the station."""
    if not SHOW_FIELD:
        return None
    if not FIELD_CSV.exists():
        return None
    f = pd.read_csv(FIELD_CSV)
    sub = f[f["station"] == mid]
    if sub.empty:
        return None
    return float(sub.sort_values("step_pair")["H1_mm"].iloc[-1])


def nice_ylim(vmin, vmax, pad_frac=0.05):
    lo = min(vmin, 0.0)
    hi = max(vmax, 0.0)
    span = hi - lo
    if span <= 0:
        span = 1.0
    p = span * pad_frac
    return (lo - p, hi + p)


def plot_full(conv, mid, mstep, ylim):
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=160)
    ax.plot(conv["step"], crown_mm(conv, mid), "-o", ms=3, lw=1.6, label="Crown settlement (z)")
    ax.plot(conv["step"], conv_mm(conv, mid), "-s", ms=3, lw=1.6, label="Sidewall convergence (-Ly+Ry)")
    ax.axvline(mstep, color="red", lw=1.3, alpha=0.8, label="Monitor step = {0}".format(mstep))
    ax.axhline(0, color="k", lw=0.8, alpha=0.5)
    fc = field_final_crown(mid)
    if fc is not None:
        ax.axhline(fc, color="green", ls="--", lw=1.4, alpha=0.85,
                   label="Field final crown H1 = {0:.1f}mm".format(fc))
    ax.set_title("full_history  monitor x={0}  (model final crown={1:.1f}mm)".format(
        mid, crown_mm(conv, mid).iloc[-1]))
    ax.set_xlabel("step (0~54)")
    ax.set_ylabel("Displacement (mm)")
    ax.set_ylim(ylim)
    ax.grid(True, alpha=0.3)

    ax2 = ax.twinx()
    ax2.plot(conv["step"], face_dist(conv, mid), color="0.35", ls=":", lw=1.5,
             drawstyle="steps-post", label="Distance from excavation face")
    ax2.set_ylabel("Distance from excavation face (m)")
    ax2.set_ylim(0, MAX_FACE_DIST)
    ax2.set_yticks([0, 10, 20, 30, 40, 50])

    l1, lab1 = ax.get_legend_handles_labels()
    l2, lab2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, lab1 + lab2, loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(DIR_FULL / "full_history_x{0}.png".format(mid), bbox_inches="tight")
    plt.close(fig)


def plot_only(cyc, mid, mstep, ylim):
    own = cyc[cyc["step"] == mstep].sort_values("cycle")
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


def plot_post(conv, mid, dstep, ylim):
    # datum = step at which the face is FACE_PAST m beyond the section;
    # only draw while still in the fine-step zone (face <= FINE_HALF m past).
    post = conv[conv["step"] >= dstep].copy().sort_values("step")
    if mid == 2608:
        post = post[post["Lxb"] <= mid + FINE_HALF]
    else:
        post = post[post["Rxa"] >= mid - FINE_HALF]
    if post.empty:
        return
    base_c = crown_mm(post, mid).iloc[0]
    base_v = conv_mm(post, mid).iloc[0]
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=160)
    ax.plot(post["step"], crown_mm(post, mid) - base_c, "-o", ms=3, lw=1.6,
            label="Crown (relative to datum)")
    ax.plot(post["step"], conv_mm(post, mid) - base_v, "-s", ms=3, lw=1.6,
            label="Convergence (relative to datum)")
    ax.axhline(0, color="k", lw=0.9, ls="--", alpha=0.7)
    ax.set_title("post_history  x={0}  (datum=face {1:.0f}m past [step {2}], fine zone only <= {3:.0f}m past)".format(
        mid, FACE_PAST, dstep, FINE_HALF))
    ax.set_xlabel("step (fine-zone range only)")
    ax.set_ylabel("Relative displacement (mm)")
    ax.set_ylim(ylim)
    ax.grid(True, alpha=0.3)

    ax2 = ax.twinx()
    ax2.plot(post["step"], face_dist(post, mid), color="0.35", ls=":", lw=1.5,
             drawstyle="steps-post", label="Distance from excavation face")
    ax2.set_ylabel("Distance from excavation face (m)")
    ax2.set_ylim(0, MAX_FACE_DIST)
    ax2.set_yticks([0, 10, 20, 30, 40, 50])

    l1, lab1 = ax.get_legend_handles_labels()
    l2, lab2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, lab1 + lab2, loc="best", fontsize=8)
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
    dsteps = {mid: datum_step(conv, mid) for mid in MONITORS}

    full_vals, only_vals, post_vals = [], [], []
    for mid in MONITORS:
        full_vals += list(crown_mm(conv, mid)) + list(conv_mm(conv, mid))
        fc = field_final_crown(mid)
        if fc is not None:
            full_vals.append(fc)
        own = cyc[cyc["step"] == msteps[mid]]
        if not own.empty:
            only_vals += list(crown_mm(own, mid)) + list(conv_mm(own, mid))
        post = conv[conv["step"] >= dsteps[mid]]
        if not post.empty:
            bc = crown_mm(post, mid).iloc[0]
            bv = conv_mm(post, mid).iloc[0]
            post_vals += list(crown_mm(post, mid) - bc) + list(conv_mm(post, mid) - bv)
    ylim_full = nice_ylim(min(full_vals), max(full_vals))
    ylim_only = nice_ylim(min(only_vals), max(only_vals)) if only_vals else (-1, 1)
    ylim_post = POST_YLIM  # fixed 0 ~ -120
    print("ylim full={0}  only={1}  post={2}".format(
        tuple(round(v) for v in ylim_full),
        tuple(round(v) for v in ylim_only),
        tuple(round(v) for v in ylim_post)))

    for mid in MONITORS:
        mstep = msteps[mid]
        dstep = dsteps[mid]
        fc = field_final_crown(mid)
        print("monitor {0}: cross-step={1}  datum-step(+{2:.0f}m)={3}  model crown={4:.1f}mm  conv={5:.1f}mm  field H1={6}".format(
            mid, mstep, FACE_PAST, dstep, crown_mm(conv, mid).iloc[-1], conv_mm(conv, mid).iloc[-1],
            "{0:.1f}mm".format(fc) if fc is not None else "n/a"))
        plot_full(conv, mid, mstep, ylim_full)
        plot_only(cyc, mid, mstep, ylim_only)
        plot_post(conv, mid, dstep, ylim_post)

    print("done ->", BASE_OUT)


if __name__ == "__main__":
    main()
