from pathlib import Path
import math

import numpy as np
import pandas as pd

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:
    raise RuntimeError("matplotlib is required for plotting") from exc


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "out" / "2d_plane_screening" / "materials_mc_plastic_zone"
SWEEP_CSV = OUT_DIR / "materials_mc_sweep_plastic_zone_along_tunnel.csv"
FIG_DIR = OUT_DIR / "plastic_zone_contours"
FIG_DIR.mkdir(parents=True, exist_ok=True)

CASE_ID = "c1.00_phip0"
B = 6.0
TUNNEL_RADIUS_M = B / 2.0
K0 = 1.2
R_LIMIT_FACTOR = 4.0


def mohr_coulomb_failure_value(sigma_1, sigma_3, cohesion_pa, phi_rad):
    return (sigma_1 - sigma_3) - (
        (sigma_1 + sigma_3) * math.sin(phi_rad)
        + 2.0 * cohesion_pa * math.cos(phi_rad)
    )


def kirsch_components_at_r_theta(vertical_stress_pa, r_m, theta_rad):
    p0 = float(vertical_stress_pa)
    r = np.asarray(r_m, dtype=float)
    theta = np.asarray(theta_rad, dtype=float)
    a = TUNNEL_RADIUS_M
    a2_r2 = (a * a) / (r * r)
    a4_r4 = a2_r2 * a2_r2
    cos2 = np.cos(2.0 * theta)
    sin2 = np.sin(2.0 * theta)

    sigma_r = 0.5 * p0 * (
        (1.0 + K0) * (1.0 - a2_r2)
        + (1.0 - K0) * (1.0 - 4.0 * a2_r2 + 3.0 * a4_r4) * cos2
    )
    sigma_theta = 0.5 * p0 * (
        (1.0 + K0) * (1.0 + a2_r2)
        - (1.0 - K0) * (1.0 + 3.0 * a4_r4) * cos2
    )
    tau_rtheta = 0.5 * p0 * (
        -(1.0 - K0) * (1.0 + 2.0 * a2_r2 - 3.0 * a4_r4) * sin2
    )
    return sigma_r, sigma_theta, tau_rtheta


def directional_plastic_boundary(vertical_stress_pa, cohesion_pa, friction_deg, n_theta=361, n_r=241):
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta)
    r_grid = np.linspace(TUNNEL_RADIUS_M, R_LIMIT_FACTOR * TUNNEL_RADIUS_M, n_r)
    phi_rad = math.radians(float(friction_deg))
    outer_radius = np.full(n_theta, TUNNEL_RADIUS_M)
    max_stability = np.full(n_theta, np.nan)
    strength_scale = max(2.0 * float(cohesion_pa) * math.cos(phi_rad), 1.0)

    for i, th in enumerate(theta):
        sigma_r, sigma_theta, tau_rtheta = kirsch_components_at_r_theta(vertical_stress_pa, r_grid, th)
        center = 0.5 * (sigma_r + sigma_theta)
        stress_radius = np.sqrt((0.5 * (sigma_r - sigma_theta)) ** 2 + tau_rtheta**2)
        sigma_1 = center + stress_radius
        sigma_3 = center - stress_radius
        failure_f = mohr_coulomb_failure_value(sigma_1, sigma_3, cohesion_pa, phi_rad)
        failed = failure_f > 0.0
        if failed.any():
            outer_radius[i] = r_grid[np.where(failed)[0].max()]
        max_stability[i] = float(np.nanmax(failure_f / strength_scale))

    return theta, np.full_like(theta, TUNNEL_RADIUS_M), outer_radius, max_stability


def pick_rows(base):
    top = base.sort_values("plastic_zone_thickness_m", ascending=False).copy()
    selected = []
    for _, row in top.iterrows():
        mileage = float(row["Mileage"])
        if all(abs(mileage - float(existing["Mileage"])) >= 80.0 for existing in selected):
            selected.append(row)
        if len(selected) >= 4:
            break

    for _, row in base.loc[base.groupby("formation_used")["plastic_zone_thickness_m"].idxmax()].iterrows():
        key = (float(row["Mileage"]), str(row["formation_used"]))
        if not any((float(existing["Mileage"]), str(existing["formation_used"])) == key for existing in selected):
            selected.append(row)
    return pd.DataFrame(selected).sort_values("plastic_zone_thickness_m", ascending=False).reset_index(drop=True)


def setup_style():
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def draw_contour(ax, row):
    theta, tunnel_r, outer_r, max_stability = directional_plastic_boundary(
        vertical_stress_pa=float(row["vertical_stress_Pa"]),
        cohesion_pa=float(row["cohesion_Pa"]),
        friction_deg=float(row["friction_deg"]),
    )
    tunnel_x = tunnel_r * np.cos(theta)
    tunnel_y = tunnel_r * np.sin(theta)
    outer_x = outer_r * np.cos(theta)
    outer_y = outer_r * np.sin(theta)

    ax.fill(outer_x, outer_y, color="#fdae6b", alpha=0.18)
    ax.fill(tunnel_x, tunnel_y, color="white", alpha=1.0)
    ax.plot(tunnel_x, tunnel_y, color="#3182bd", linewidth=2.0, label="Tunnel")
    ax.plot(outer_x, outer_y, color="#e6550d", linewidth=2.2, label="Plastic boundary")

    pz = outer_r - tunnel_r
    max_idx = int(np.nanargmax(pz))
    ax.plot([0.0, outer_x[max_idx]], [0.0, outer_y[max_idx]], color="#de2d26", linewidth=1.1, linestyle="--")
    ax.scatter([outer_x[max_idx]], [outer_y[max_idx]], color="#de2d26", s=22, zorder=5)

    limit = max(float(np.nanmax(outer_r)) * 1.12, TUNNEL_RADIUS_M * 2.0)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.axhline(0.0, color="#bdbdbd", linewidth=0.8)
    ax.axvline(0.0, color="#bdbdbd", linewidth=0.8)
    ax.grid(color="#d9d9d9", linewidth=0.9)
    ax.set_title(
        f"Mileage {float(row['Mileage']):.0f} | {row['formation_used']} | K0={K0}\n"
        f"max plastic={float(np.nanmax(pz)):.2f} m, c={float(row['cohesion_kPa']):.1f} kPa, phi={float(row['friction_deg']):.1f}°",
        fontsize=10,
    )
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    return {
        "directional_max_plastic_m": float(np.nanmax(pz)),
        "directional_mean_plastic_m": float(np.nanmean(pz)),
        "directional_max_angle_deg": float(np.degrees(theta[max_idx])),
        "directional_max_stability_index": float(np.nanmax(max_stability)),
    }


def draw_stress_vs_r(row, theta_deg=0.0):
    r_grid = np.linspace(TUNNEL_RADIUS_M, R_LIMIT_FACTOR * TUNNEL_RADIUS_M, 80)
    theta_rad = math.radians(theta_deg)
    sigma_r, sigma_theta, tau_rtheta = kirsch_components_at_r_theta(
        vertical_stress_pa=float(row["vertical_stress_Pa"]),
        r_m=r_grid,
        theta_rad=theta_rad,
    )

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.plot(r_grid, sigma_r / 1000.0, color="#3182bd", marker="o", markevery=10, label="σr radial")
    ax.plot(r_grid, sigma_theta / 1000.0, color="#e6550d", marker="o", markevery=10, label="σθ tangential")
    ax.plot(r_grid, tau_rtheta / 1000.0, color="#969696", marker="o", markevery=10, label="τrθ shear")
    ax.axvline(TUNNEL_RADIUS_M, color="#636363", linewidth=1.0, linestyle="--", label="tunnel wall")
    ax.set_xlabel("r (m)")
    ax.set_ylabel("stress (kPa)")
    ax.set_title(f"Mileage {float(row['Mileage']):.0f} | {row['formation_used']} | K0={K0} | θ={theta_deg:.0f}°")
    ax.grid(alpha=0.28)
    ax.legend(loc="best")
    fig.tight_layout()
    png = FIG_DIR / f"{CASE_ID}_mileage_{int(round(float(row['Mileage']))):04d}_{row['formation_used']}_stress_r_theta{theta_deg:.0f}.png"
    fig.savefig(png, dpi=220)
    plt.close(fig)
    return png


def main():
    setup_style()
    data = pd.read_csv(SWEEP_CSV, encoding="utf-8-sig")
    base = data[data["case_id"].eq(CASE_ID)].copy()
    if base.empty:
        raise ValueError(f"No rows found for case_id={CASE_ID}")

    selected = pick_rows(base)
    detail_rows = []
    for _, row in selected.iterrows():
        fig, ax = plt.subplots(figsize=(7.5, 7.5))
        detail = draw_contour(ax, row)
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.12), ncol=2)
        fig.tight_layout()
        contour_png = FIG_DIR / f"{CASE_ID}_mileage_{int(round(float(row['Mileage']))):04d}_{row['formation_used']}.png"
        fig.savefig(contour_png, dpi=220, bbox_inches="tight")
        plt.close(fig)

        stress_png = draw_stress_vs_r(row, theta_deg=0.0)
        record = row.to_dict()
        record.update(detail)
        record["contour_png"] = str(contour_png)
        record["stress_r_png"] = str(stress_png)
        detail_rows.append(record)

    detail_df = pd.DataFrame(detail_rows)
    selected_csv = FIG_DIR / f"{CASE_ID}_selected_large_plastic_mileages.csv"
    detail_df.to_csv(selected_csv, index=False, encoding="utf-8-sig")

    ncols = 2
    nrows = int(math.ceil(len(selected) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 7 * nrows), squeeze=False)
    for ax in axes.ravel():
        ax.set_visible(False)
    for ax, (_, row) in zip(axes.ravel(), selected.iterrows()):
        ax.set_visible(True)
        draw_contour(ax, row)
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2)
    fig.suptitle(f"Tunnel contour and estimated plastic-zone boundary ({CASE_ID})", fontsize=15)
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    overview_png = FIG_DIR / f"{CASE_ID}_large_plastic_mileage_contours_overview.png"
    fig.savefig(overview_png, dpi=220)
    plt.close(fig)

    print(f"selected_csv={selected_csv}")
    print(f"overview_png={overview_png}")
    print(detail_df[["Mileage", "formation_used", "plastic_zone_thickness_m", "directional_max_plastic_m", "directional_max_angle_deg", "contour_png", "stress_r_png"]].to_string(index=False))


if __name__ == "__main__":
    main()
