from pathlib import Path
import math

import numpy as np
import pandas as pd

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:
    plt = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GEOMETRY_CSV = PROJECT_ROOT / "out" / "2d_plane_screening" / "parameter_sweep" / "01_2d_plane_screening_geometry_base.csv"
OUT_DIR = PROJECT_ROOT / "out" / "2d_plane_screening" / "materials_mc_plastic_zone"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# (density[kg/m3], young[GPa], poisson[-], cohesion[kPa], friction[deg],)
materials_mc_base = {
    "SS_NK": (2565.0, 1.2e9, 0.29, 220e3, 35.0),
    "Interbedded_ST": (2520.0, 0.6e9, 0.32, 145e3, 30.0),
    "SH_ST": (2538.0, 0.8e9, 0.38, 100e3, 28.0),
    "SS_NC": (2485.0, 1.0e9, 0.25, 300e3, 42.0),
    "Fault": (2490.0, 0.3e9, 0.30, 27e3, 17.0),
}

C_SCALES = [0.75, 1.00, 1.25]
PHI_DELTAS_DEG = [-3.0, 0.0, 3.0]

B = 6.0
TUNNEL_RADIUS_M = B / 2.0
K0 = 1.2
G = 9.81

R_LIMIT_FACTOR = 4.0
R_SAMPLES = 97
THETA_SAMPLES = 73
CHUNK_SIZE = 128


def kirsch_components(vertical_stress_pa, r_m, theta_rad):
    p0 = np.asarray(vertical_stress_pa, dtype=float)[:, None, None]
    r = np.asarray(r_m, dtype=float)[None, :, None]
    theta = np.asarray(theta_rad, dtype=float)[None, None, :]
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


def mohr_coulomb_failure_value(sigma_1, sigma_3, cohesion_pa, phi_rad):
    return (sigma_1 - sigma_3) - (
        (sigma_1 + sigma_3) * math.sin(phi_rad)
        + 2.0 * cohesion_pa * math.cos(phi_rad)
    )


def estimate_plastic_zone_mc(vertical_stress_pa, cohesion_pa, friction_deg):
    vertical_stress_pa = np.asarray(vertical_stress_pa, dtype=float)
    n_rows = len(vertical_stress_pa)
    cohesion_pa = float(cohesion_pa)
    phi_rad = math.radians(float(friction_deg))

    r_grid = np.linspace(TUNNEL_RADIUS_M, R_LIMIT_FACTOR * TUNNEL_RADIUS_M, R_SAMPLES)
    theta_grid = np.linspace(0.0, 2.0 * math.pi, THETA_SAMPLES)

    plastic_radius_m = np.full(n_rows, TUNNEL_RADIUS_M)
    max_failure_f_pa = np.full(n_rows, np.nan)
    max_sigma_1_pa = np.full(n_rows, np.nan)
    max_sigma_3_pa = np.full(n_rows, np.nan)
    plastic_theta_deg = np.zeros(n_rows)
    stability_index = np.full(n_rows, np.nan)

    strength_scale = max(2.0 * cohesion_pa * math.cos(phi_rad), 1.0)

    for start in range(0, n_rows, CHUNK_SIZE):
        end = min(start + CHUNK_SIZE, n_rows)
        p0 = vertical_stress_pa[start:end]
        sigma_r, sigma_theta, tau_rtheta = kirsch_components(p0, r_grid, theta_grid)
        center = 0.5 * (sigma_r + sigma_theta)
        stress_radius = np.sqrt((0.5 * (sigma_r - sigma_theta)) ** 2 + tau_rtheta**2)
        sigma_1 = center + stress_radius
        sigma_3 = center - stress_radius
        failure_f = mohr_coulomb_failure_value(sigma_1, sigma_3, cohesion_pa, phi_rad)

        failed_by_r = (failure_f > 0.0).any(axis=2)
        any_failed = failed_by_r.any(axis=1)
        reverse_idx = np.argmax(failed_by_r[:, ::-1], axis=1)
        last_failed_idx = (R_SAMPLES - 1) - reverse_idx
        local_radius = np.where(any_failed, r_grid[last_failed_idx], TUNNEL_RADIUS_M)

        flat_idx = np.nanargmax(failure_f.reshape(end - start, -1), axis=1)
        max_r_idx = flat_idx // THETA_SAMPLES
        max_theta_idx = flat_idx % THETA_SAMPLES
        row_idx = np.arange(end - start)

        plastic_radius_m[start:end] = local_radius
        max_failure_f_pa[start:end] = failure_f.reshape(end - start, -1)[row_idx, flat_idx]
        max_sigma_1_pa[start:end] = sigma_1[row_idx, max_r_idx, max_theta_idx]
        max_sigma_3_pa[start:end] = sigma_3[row_idx, max_r_idx, max_theta_idx]
        plastic_theta_deg[start:end] = np.degrees(theta_grid[max_theta_idx])
        stability_index[start:end] = max_failure_f_pa[start:end] / strength_scale

    plastic_radius_m[vertical_stress_pa <= 0.0] = TUNNEL_RADIUS_M
    plastic_thickness_m = plastic_radius_m - TUNNEL_RADIUS_M
    plastic_ratio = plastic_thickness_m / TUNNEL_RADIUS_M

    yield_state = np.full(n_rows, "elastic", dtype=object)
    yield_state[plastic_thickness_m > 0.0] = "plastic_estimate"
    yield_state[np.isclose(plastic_radius_m, R_LIMIT_FACTOR * TUNNEL_RADIUS_M)] = "plastic_reaches_4a_estimate"
    yield_state[vertical_stress_pa <= 0.0] = "no_overburden"

    return {
        "plastic_zone_thickness_m": plastic_thickness_m,
        "plastic_zone_ratio_to_radius": plastic_ratio,
        "plastic_radius_m": plastic_radius_m,
        "plastic_theta_deg": plastic_theta_deg,
        "max_failure_F_Pa": max_failure_f_pa,
        "max_sigma_1_Pa": max_sigma_1_pa,
        "max_sigma_3_Pa": max_sigma_3_pa,
        "stability_index": stability_index,
        "yield_state": yield_state,
    }


def build_cases():
    cases = []
    for c_scale in C_SCALES:
        for phi_delta in PHI_DELTAS_DEG:
            case_id = f"c{c_scale:.2f}_phi{phi_delta:+.0f}".replace("+", "p").replace("-", "m")
            case_materials = {}
            for formation, values in materials_mc_base.items():
                density, young_pa, poisson, cohesion_pa, friction_deg = values
                case_materials[formation] = (
                    density,
                    young_pa,
                    poisson,
                    cohesion_pa * c_scale,
                    friction_deg + phi_delta,
                )
            cases.append({"case_id": case_id, "c_scale": c_scale, "phi_delta_deg": phi_delta, "materials": case_materials})
    return cases


def run_case(geometry, case):
    rows = []
    for formation, group in geometry.groupby("formation_used", sort=False):
        density, young_pa, poisson, cohesion_pa, friction_deg = case["materials"][formation]
        vertical_stress_pa = density * G * group["overburden_m"].to_numpy(dtype=float)
        plastic = estimate_plastic_zone_mc(vertical_stress_pa, cohesion_pa, friction_deg)

        local = group.copy()
        local["case_id"] = case["case_id"]
        local["c_scale"] = case["c_scale"]
        local["phi_delta_deg"] = case["phi_delta_deg"]
        local["density_kg_m3"] = density
        local["young_Pa"] = young_pa
        local["young_GPa"] = young_pa / 1.0e9
        local["poisson"] = poisson
        local["cohesion_kPa"] = cohesion_pa / 1.0e3
        local["cohesion_Pa"] = cohesion_pa
        local["cohesion_MPa"] = cohesion_pa / 1.0e6
        local["friction_deg"] = friction_deg
        local["vertical_stress_Pa"] = vertical_stress_pa
        local["horizontal_stress_Pa"] = K0 * vertical_stress_pa
        local["failure_criterion"] = "Mohr-Coulomb"
        local["plastic_zone_method"] = "Kirsch_r_theta_scan_to_4a"
        for key, value in plastic.items():
            local[key] = value
        rows.append(local)
    return pd.concat(rows, ignore_index=True)


def summarize_results(result):
    by_case_formation = (
        result.groupby(["case_id", "c_scale", "phi_delta_deg", "formation_used"])
        .agg(
            n_points=("Mileage", "count"),
            mileage_min=("Mileage", "min"),
            mileage_max=("Mileage", "max"),
            overburden_max_m=("overburden_m", "max"),
            plastic_mean_m=("plastic_zone_thickness_m", "mean"),
            plastic_p50_m=("plastic_zone_thickness_m", "median"),
            plastic_p95_m=("plastic_zone_thickness_m", lambda x: float(np.quantile(x, 0.95))),
            plastic_max_m=("plastic_zone_thickness_m", "max"),
            plastic_ratio_max=("plastic_zone_ratio_to_radius", "max"),
            stability_index_max=("stability_index", "max"),
        )
        .reset_index()
    )
    by_case = (
        by_case_formation.groupby(["case_id", "c_scale", "phi_delta_deg"])
        .agg(
            plastic_mean_max_formation_m=("plastic_mean_m", "max"),
            plastic_p50_max_formation_m=("plastic_p50_m", "max"),
            plastic_p95_max_formation_m=("plastic_p95_m", "max"),
            plastic_max_m=("plastic_max_m", "max"),
            plastic_ratio_max=("plastic_ratio_max", "max"),
            stability_index_max=("stability_index_max", "max"),
        )
        .reset_index()
        .sort_values(["plastic_p95_max_formation_m", "plastic_max_m"])
    )
    return by_case, by_case_formation


def write_material_table(cases):
    rows = []
    for case in cases:
        for formation, values in case["materials"].items():
            density, young_pa, poisson, cohesion_pa, friction_deg = values
            rows.append(
                {
                    "case_id": case["case_id"],
                    "c_scale": case["c_scale"],
                    "phi_delta_deg": case["phi_delta_deg"],
                    "formation": formation,
                    "density_kg_m3": density,
                    "young_Pa": young_pa,
                    "young_GPa": young_pa / 1.0e9,
                    "poisson": poisson,
                    "cohesion_kPa": cohesion_pa / 1.0e3,
                    "cohesion_Pa": cohesion_pa,
                    "cohesion_MPa": cohesion_pa / 1.0e6,
                    "friction_deg": friction_deg,
                }
            )
    material_csv = OUT_DIR / "materials_mc_sweep_used.csv"
    pd.DataFrame(rows).to_csv(material_csv, index=False, encoding="utf-8-sig")
    return material_csv


def write_figures(result, by_case, by_case_formation):
    if plt is None:
        return {}

    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    figures = {}
    base_case = "c1.00_phip0"

    fig, ax = plt.subplots(figsize=(13.5, 5.5))
    for case_id, group in result.groupby("case_id", sort=False):
        per_mileage = group.groupby("Mileage")["plastic_zone_thickness_m"].max().reset_index()
        is_base = case_id == base_case
        ax.plot(per_mileage["Mileage"], per_mileage["plastic_zone_thickness_m"], linewidth=2.2 if is_base else 0.9, alpha=0.95 if is_base else 0.45, label=case_id if is_base else None, color="#de2d26" if is_base else "#636363")
    ax.set_xlabel("Mileage")
    ax.set_ylabel("Max plastic zone thickness by mileage (m)")
    ax.set_title("Plastic zone thickness along tunnel: c/phi sweep")
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    path = OUT_DIR / "materials_mc_sweep_plastic_zone_along_tunnel.png"
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    figures["along_tunnel_sweep_png"] = str(path)

    ordered = by_case.sort_values("plastic_p95_max_formation_m").reset_index(drop=True)
    x = np.arange(len(ordered))
    fig, ax = plt.subplots(figsize=(12.5, 5.8))
    ax.bar(x, ordered["plastic_max_m"], color="#9ecae1", label="max")
    ax.plot(x, ordered["plastic_p95_max_formation_m"], color="#de2d26", marker="o", label="max formation P95")
    ax.plot(x, ordered["plastic_p50_max_formation_m"], color="#31a354", marker="s", label="max formation P50")
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["case_id"], rotation=45, ha="right")
    ax.set_ylabel("Plastic zone thickness (m)")
    ax.set_title("Plastic zone statistics by c/phi case")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    path = OUT_DIR / "materials_mc_sweep_plastic_zone_statistics.png"
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    figures["statistics_png"] = str(path)

    pivot = by_case.pivot(index="phi_delta_deg", columns="c_scale", values="plastic_p95_max_formation_m")
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    im = ax.imshow(pivot.to_numpy(dtype=float), cmap="viridis_r", aspect="auto")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([f"{v:.2f}" for v in pivot.columns])
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([f"{v:+.0f}" for v in pivot.index])
    ax.set_xlabel("cohesion scale")
    ax.set_ylabel("friction delta (deg)")
    ax.set_title("P95 plastic zone heatmap (smaller is better)")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, f"{pivot.iloc[i, j]:.2f}", ha="center", va="center", color="white")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("max formation P95 plastic zone (m)")
    path = OUT_DIR / "materials_mc_sweep_c_phi_heatmap.png"
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    figures["c_phi_heatmap_png"] = str(path)
    return figures


def main():
    geometry = pd.read_csv(GEOMETRY_CSV, encoding="utf-8-sig")
    cases = build_cases()
    result = pd.concat([run_case(geometry, case) for case in cases], ignore_index=True)
    result = result.sort_values(["case_id", "Mileage"]).reset_index(drop=True)

    result_csv = OUT_DIR / "materials_mc_sweep_plastic_zone_along_tunnel.csv"
    result.to_csv(result_csv, index=False, encoding="utf-8-sig")
    by_case, by_case_formation = summarize_results(result)
    summary_case_csv = OUT_DIR / "materials_mc_sweep_summary_by_case.csv"
    summary_formation_csv = OUT_DIR / "materials_mc_sweep_summary_by_case_formation.csv"
    by_case.to_csv(summary_case_csv, index=False, encoding="utf-8-sig")
    by_case_formation.to_csv(summary_formation_csv, index=False, encoding="utf-8-sig")
    material_csv = write_material_table(cases)
    figures = write_figures(result, by_case, by_case_formation)

    print(f"result_csv={result_csv}")
    print(f"summary_case_csv={summary_case_csv}")
    print(f"summary_formation_csv={summary_formation_csv}")
    print(f"material_csv={material_csv}")
    for name, path in figures.items():
        print(f"{name}={path}")
    print()
    print("Best cases by max formation P95 plastic zone:")
    print(by_case.head(9).to_string(index=False))


if __name__ == "__main__":
    main()
