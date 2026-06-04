from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:
    plt = None


# ============================================================
# Stage 1：2D 解析解無支撐岩體參數快速篩選
# ============================================================

# 本階段只篩選岩體參數，不加入噴凝土、支護壓力、shell、liner 或 equivalent support。
# 位移為解析解快速估算值，塑性區為 Kirsch + Mohr-Coulomb 快速網格估算值。

WORKFLOW_NAME = "stage1_2d_unsupported_plastic_hb_screening"
SCREENING_MODE = "plastic_zone_only"
FAILURE_CRITERION = "generalized_hoek_brown"
HB_DISTURBANCE_D = 0.5

N_PARAMETER_SETS = 100
RANDOM_SEED = 20260527

B = 6.0
D = B
a = D / 2.0
K0 = 1.2
g = 9.81

DISPLACEMENT_MODEL = "disabled_plastic_zone_only"
DISPLACEMENT_MODEL_NOTE = (
    "Settlement/convergence estimates are disabled in this run because Stage 1 "
    "is used only for plastic-zone screening."
)

PLASTIC_RADIUS_LIMIT_FACTOR = 4.0
PLASTIC_RADIUS_SAMPLES = 1
PLASTIC_THETA_SAMPLES = 37
PLASTIC_ZONE_INDEX_SCALE = 0.35

HARD_LIMITS = {
    "plastic_zone_ratio_to_radius": 2.0,
    "friction_min_deg": 0.0,
    "friction_max_deg": 60.0,
}

RECOMMENDED_STAGE2_COUNT = 20
WRITE_DETAILED_BY_MILEAGE = False


def find_project_root() -> Path:
    """讓 notebook 從 2D 或 2D/code 執行都能找到專案根目錄。"""
    project_root = Path.cwd().resolve()
    if not (project_root / "int").exists() and (project_root.parent / "int").exists():
        project_root = project_root.parent
    return project_root


workdir = find_project_root()
input_dir = workdir / "int"
output_dir = workdir / "out" / "2d_plane_screening" / "parameter_sweep"
output_dir.mkdir(parents=True, exist_ok=True)
figure_dir = output_dir / "figures"
figure_dir.mkdir(parents=True, exist_ok=True)

if plt is not None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft JhengHei",
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

geometry_base_csv = output_dir / "01_2d_plane_screening_geometry_base.csv"
previous_result_csv = output_dir / "01_2d_plane_screening_results.csv"
legacy_root_result_csv = workdir / "01_2d_plane_screening_results.csv"

material_stats_candidates = [
    input_dir / "00_material_parameter_statistics.csv",
    input_dir / "0.00_material_parameter_statistics.csv",
]
material_stats_csv = next((p for p in material_stats_candidates if p.exists()), None)
if material_stats_csv is None:
    raise FileNotFoundError(
        "找不到材料統計檔，已檢查："
        + ", ".join(str(p) for p in material_stats_candidates)
    )


def read_geometry() -> pd.DataFrame:
    """讀取已建立好的 2D 幾何基礎表，不重新處理 PLY。"""
    if geometry_base_csv.exists():
        geometry_source_csv = geometry_base_csv
    elif previous_result_csv.exists():
        geometry_source_csv = previous_result_csv
    elif legacy_root_result_csv.exists():
        geometry_source_csv = legacy_root_result_csv
    else:
        raise FileNotFoundError(
            "找不到幾何基礎檔，請先建立 01_2d_plane_screening_geometry_base.csv。"
        )

    raw_geometry = pd.read_csv(geometry_source_csv, encoding="utf-8-sig", low_memory=False)
    geometry_columns = [
        "Mileage",
        "excavation_distance_m",
        "X_local",
        "Y_local",
        "Z_crown",
        "Z_topography",
        "overburden_m",
        "formation_nearest",
        "formation_used",
    ]
    missing_columns = [c for c in geometry_columns if c not in raw_geometry.columns]
    if missing_columns:
        raise ValueError(f"幾何資料缺少必要欄位：{missing_columns}")

    geometry = raw_geometry[geometry_columns].drop_duplicates(subset=["Mileage"]).copy()
    geometry = geometry.sort_values("Mileage").reset_index(drop=True)
    geometry["overburden_m"] = pd.to_numeric(geometry["overburden_m"], errors="coerce")
    geometry["overburden_m"] = geometry["overburden_m"].clip(lower=0.0)
    geometry.to_csv(geometry_base_csv, index=False, encoding="utf-8-sig")
    return geometry


def read_material_statistics() -> pd.DataFrame:
    """讀取材料 min~max 統計值。"""
    stats = pd.read_csv(material_stats_csv, encoding="utf-8-sig")
    required_columns = {"formation", "parameter", "min", "max"}
    missing_columns = sorted(required_columns - set(stats.columns))
    if missing_columns:
        raise ValueError(f"材料統計檔缺少必要欄位：{missing_columns}")

    stats["formation"] = stats["formation"].astype(str).str.strip()
    stats["parameter"] = stats["parameter"].astype(str).str.strip()
    if "unit" not in stats.columns:
        stats["unit"] = ""
    return stats


def to_float(value) -> float:
    value = pd.to_numeric(value, errors="coerce")
    return float(value) if np.isfinite(value) else np.nan


def get_parameter_range(table: pd.DataFrame, names: list[str]) -> tuple[float, float, str, str]:
    """依照可能欄位名稱取得 min/max。"""
    indexed = table.set_index("parameter", drop=False)
    for name in names:
        if name in indexed.index:
            row = indexed.loc[name]
            vmin = to_float(row["min"])
            vmax = to_float(row["max"])
            unit = str(row.get("unit", ""))
            if not np.isfinite(vmin) or not np.isfinite(vmax):
                raise ValueError(f"{table.iloc[0]['formation']} 的 {name} min/max 不是有效數字")
            if vmax < vmin:
                raise ValueError(f"{table.iloc[0]['formation']} 的 {name} max 小於 min")
            return vmin, vmax, name, unit

    formation = table.iloc[0]["formation"] if len(table) else "unknown"
    raise ValueError(f"{formation} 缺少必要材料參數：{names}")


def unit_factor(parameter_name: str, unit: str) -> float:
    """把 MPa 轉成 Pa，其餘單位維持原值。"""
    name = parameter_name.lower()
    unit_text = str(unit).lower()
    if name.endswith("_gpa") or unit_text == "gpa":
        return 1.0e9
    if name.endswith("_mpa") or unit_text == "mpa":
        return 1.0e6
    return 1.0


def hoek_brown_constants(mi: float, gsi: float, disturbance_d: float) -> tuple[float, float, float]:
    mb = float(mi) * math.exp((float(gsi) - 100.0) / (28.0 - 14.0 * float(disturbance_d)))
    s = math.exp((float(gsi) - 100.0) / (9.0 - 3.0 * float(disturbance_d)))
    hb_a = 0.5 + (math.exp(-float(gsi) / 15.0) - math.exp(-20.0 / 3.0)) / 6.0
    return mb, s, hb_a


def build_candidate_material_table(geometry: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    """每個 formation 的每個材料參數都用 min~max 取 100 個值，再用固定亂數排列組合。"""
    rng = np.random.default_rng(RANDOM_SEED)
    geometry_formations = set(geometry["formation_used"].dropna().astype(str).unique())
    formations = sorted(stats["formation"].dropna().astype(str).unique())

    parameter_specs = [
        ("density", ["density_kg_m3", "density"]),
        ("E", ["E_GPa", "E_MPa", "E"]),
        ("poisson", ["nu", "poisson"]),
        ("cohesion", ["c_MPa", "c_GPa", "cohesion", "c"]),
        ("friction", ["phi_deg", "friction", "friction_deg", "phi"]),
        ("sigma_ci", ["sigma_ci_MPa", "UCS_MPa", "ucs_MPa", "sigma_ci"]),
        ("mi", ["mi"]),
        ("GSI", ["GSI", "gsi"]),
        ("disturbance_D", ["D_hb", "disturbance_D", "D"]),
    ]

    formation_grids = {}
    for formation in formations:
        table = stats[stats["formation"] == formation].copy()
        if table.empty:
            raise ValueError(f"材料統計檔沒有 formation：{formation}")

        formation_grids[formation] = {}
        for output_name, aliases in parameter_specs:
            vmin, vmax, source_name, unit = get_parameter_range(table, aliases)
            factor = unit_factor(source_name, unit)
            values = np.linspace(vmin, vmax, N_PARAMETER_SETS) * factor
            if np.isclose(values[0], values[-1]):
                positions = np.full(N_PARAMETER_SETS, 0.5)
                permuted_values = values.copy()
                permuted_positions = positions.copy()
            else:
                positions = np.linspace(0.0, 1.0, N_PARAMETER_SETS)
                order = rng.permutation(N_PARAMETER_SETS)
                permuted_values = values[order]
                permuted_positions = positions[order]

            formation_grids[formation][output_name] = {
                "values": permuted_values,
                "positions": permuted_positions,
                "source_name": source_name,
                "unit": unit,
                "min": values[0],
                "max": values[-1],
            }

    records = []
    for i in range(N_PARAMETER_SETS):
        parameter_set_id = f"P{i + 1:04d}"
        for formation in formations:
            item = {
                "parameter_set_id": parameter_set_id,
                "parameter_level": "min_max_sweep_100_lhs",
                "formation": formation,
                "formation_used": formation,
                "material_group": formation,
                "used_in_stage1_geometry": formation in geometry_formations,
                "tension": np.nan,
                "dilation": np.nan,
            }
            for output_name, _ in parameter_specs:
                grid = formation_grids[formation][output_name]
                item[output_name] = float(grid["values"][i])
                item[f"{output_name}_position_0_1"] = float(grid["positions"][i])
                item[f"{output_name}_source_parameter"] = grid["source_name"]
                item[f"{output_name}_source_unit"] = grid["unit"]
            item["gamma_N_m3"] = item["density"] * g
            item["E_GPa"] = item["E"] / 1.0e9
            item["cohesion_MPa"] = item["cohesion"] / 1.0e6
            item["sigma_ci_MPa"] = item["sigma_ci"] / 1.0e6
            hb_mb, hb_s, hb_a = hoek_brown_constants(
                item["mi"],
                item["GSI"],
                item["disturbance_D"],
            )
            item["hb_mb"] = hb_mb
            item["hb_s"] = hb_s
            item["hb_a"] = hb_a
            records.append(item)

    return pd.DataFrame(records)


def mohr_coulomb_failure_value(sigma_1, sigma_3, cohesion, phi_rad):
    """F >= 0 代表該點達到 Mohr-Coulomb 破壞條件。"""
    return (sigma_1 - sigma_3) - (
        (sigma_1 + sigma_3) * math.sin(phi_rad)
        + 2.0 * cohesion * math.cos(phi_rad)
    )


def hoek_brown_failure_value(sigma_1, sigma_3, sigma_ci, hb_mb, hb_s, hb_a):
    """Return positive values where the local stress exceeds the generalized Hoek-Brown envelope."""
    sigma_3_eff = np.maximum(np.asarray(sigma_3, dtype=float), 0.0)
    sigma_ci = max(float(sigma_ci), 1.0)
    hb_base = np.maximum(float(hb_mb) * sigma_3_eff / sigma_ci + float(hb_s), 0.0)
    sigma_1_hb = sigma_3_eff + sigma_ci * np.power(hb_base, float(hb_a))
    return np.asarray(sigma_1, dtype=float) - sigma_1_hb


def estimate_plastic_zone(
    vertical_stress_Pa: np.ndarray,
    cohesion: float,
    friction_deg: float,
    sigma_ci: float,
    hb_mb: float,
    hb_s: float,
    hb_a: float,
) -> dict[str, np.ndarray]:
    """用洞壁 Kirsch 應力場快速估算塑性區，輸出 estimate 欄位。"""
    vertical_stress_Pa = np.asarray(vertical_stress_Pa, dtype=float)
    n_rows = len(vertical_stress_Pa)

    radius_limit_m = PLASTIC_RADIUS_LIMIT_FACTOR * a
    theta_rad = np.linspace(0.0, math.pi, PLASTIC_THETA_SAMPLES)
    theta_deg = np.degrees(theta_rad)

    phi_rad = math.radians(float(friction_deg))
    p0 = vertical_stress_Pa[:, None]
    theta = theta_rad[None, :]
    cos2 = np.cos(2.0 * theta)
    sin2 = np.sin(2.0 * theta)

    # 洞壁 r=a，無支撐內壓為 0；這裡只做快速篩選，不做細網格塑性半徑解析。
    a2_r2 = 1.0
    a4_r4 = 1.0
    sigma_r = 0.5 * p0 * (
        (1.0 + K0) * (1.0 - a2_r2)
        + (1.0 - K0) * (1.0 - 4.0 * a2_r2 + 3.0 * a4_r4) * cos2
    )
    sigma_theta = 0.5 * p0 * (
        (1.0 + K0) * (1.0 + a2_r2)
        - (1.0 - K0) * (1.0 + 3.0 * a4_r4) * cos2
    )
    tau_rtheta = -0.5 * p0 * (
        (1.0 - K0) * (1.0 + 2.0 * a2_r2 - 3.0 * a4_r4) * sin2
    )

    center = 0.5 * (sigma_r + sigma_theta)
    stress_radius = np.sqrt((0.5 * (sigma_r - sigma_theta)) ** 2 + tau_rtheta ** 2)
    sigma_1 = center + stress_radius
    sigma_3 = center - stress_radius
    failure_F = hoek_brown_failure_value(
        sigma_1=sigma_1,
        sigma_3=sigma_3,
        sigma_ci=sigma_ci,
        hb_mb=hb_mb,
        hb_s=hb_s,
        hb_a=hb_a,
    )

    local_idx = np.nanargmax(failure_F, axis=1)
    max_failure_F_Pa = failure_F[np.arange(n_rows), local_idx]
    max_sigma_1_Pa = sigma_1[np.arange(n_rows), local_idx]
    max_sigma_3_Pa = sigma_3[np.arange(n_rows), local_idx]
    plastic_theta_deg = theta_deg[local_idx]

    no_overburden = vertical_stress_Pa <= 0.0
    strength_scale = max(float(sigma_ci) * (max(float(hb_s), 0.0) ** float(hb_a)), 1.0)
    stability_index = max_failure_F_Pa / strength_scale
    positive_index = np.maximum(stability_index, 0.0)
    plastic_ratio = np.minimum(
        PLASTIC_RADIUS_LIMIT_FACTOR - 1.0,
        PLASTIC_ZONE_INDEX_SCALE * np.log1p(positive_index),
    )
    plastic_ratio[no_overburden] = 0.0
    plastic_thickness_m = plastic_ratio * a
    plastic_radius_m = a + plastic_thickness_m

    yield_state = np.full(n_rows, "elastic", dtype=object)
    yield_state[plastic_thickness_m > 0.0] = "plastic_estimate"
    reaches_limit = np.isclose(plastic_radius_m, radius_limit_m)
    yield_state[reaches_limit] = "plastic_reaches_4a_estimate"
    yield_state[no_overburden] = "no_overburden"

    return {
        "plastic_radius_estimate_m": plastic_radius_m,
        "plastic_zone_thickness_estimate_m": plastic_thickness_m,
        "plastic_zone_ratio_to_radius": plastic_ratio,
        "plastic_theta_estimate_deg": plastic_theta_deg,
        "plastic_check_limit_m": np.full(n_rows, radius_limit_m),
        "max_failure_F_Pa": max_failure_F_Pa,
        "max_sigma_1_Pa": max_sigma_1_Pa,
        "max_sigma_3_Pa": max_sigma_3_Pa,
        "stability_index": stability_index,
        "yield_state": yield_state,
        "failure_criterion": np.full(n_rows, FAILURE_CRITERION, dtype=object),
        "hb_sigma_ci_MPa": np.full(n_rows, float(sigma_ci) / 1.0e6),
        "hb_mb": np.full(n_rows, float(hb_mb)),
        "hb_s": np.full(n_rows, float(hb_s)),
        "hb_a": np.full(n_rows, float(hb_a)),
    }


def run_stage1_screening(geometry: pd.DataFrame, material_table: pd.DataFrame) -> pd.DataFrame:
    """對每一組全域參數組合，沿隧道里程計算 2D 無支撐快速估算結果。"""
    result_frames = []

    for parameter_set_id, candidate_materials in material_table.groupby("parameter_set_id", sort=False):
        material_lookup = candidate_materials.set_index("formation_used", drop=False)

        for formation, group in geometry.groupby("formation_used", sort=False):
            if formation not in material_lookup.index:
                raise ValueError(f"{parameter_set_id} 缺少 formation 參數：{formation}")

            mat = material_lookup.loc[formation]
            local = group.copy()
            vertical_stress = mat["gamma_N_m3"] * local["overburden_m"].to_numpy(dtype=float)
            horizontal_stress = K0 * vertical_stress
            mean_stress = 0.5 * (vertical_stress + horizontal_stress)
            radial_convergence_m = np.full(len(local), np.nan)

            plastic = estimate_plastic_zone(
                vertical_stress_Pa=vertical_stress,
                cohesion=float(mat["cohesion"]),
                friction_deg=float(mat["friction"]),
                sigma_ci=float(mat["sigma_ci"]),
                hb_mb=float(mat["hb_mb"]),
                hb_s=float(mat["hb_s"]),
                hb_a=float(mat["hb_a"]),
            )

            local["parameter_set_id"] = parameter_set_id
            local["parameter_level"] = mat["parameter_level"]
            local["formation"] = formation
            local["material_group"] = formation
            local["tunnel_diameter_m"] = D
            local["tunnel_radius_m"] = a
            local["K0"] = K0
            local["initial_stress_condition"] = "vertical_stress_from_overburden_horizontal_equals_K0_vertical"
            local["density"] = float(mat["density"])
            local["gamma_N_m3"] = float(mat["gamma_N_m3"])
            local["E"] = float(mat["E"])
            local["cohesion"] = float(mat["cohesion"])
            local["friction"] = float(mat["friction"])
            local["sigma_ci"] = float(mat["sigma_ci"])
            local["sigma_ci_MPa"] = float(mat["sigma_ci_MPa"])
            local["mi"] = float(mat["mi"])
            local["GSI"] = float(mat["GSI"])
            local["disturbance_D"] = float(mat["disturbance_D"])
            local["hb_mb"] = float(mat["hb_mb"])
            local["hb_s"] = float(mat["hb_s"])
            local["hb_a"] = float(mat["hb_a"])
            local["poisson"] = float(mat["poisson"])
            local["tension"] = np.nan
            local["dilation"] = np.nan
            local["vertical_stress_Pa"] = vertical_stress
            local["horizontal_stress_Pa"] = horizontal_stress
            local["mean_in_situ_stress_Pa"] = mean_stress
            local["radial_convergence_m"] = radial_convergence_m
            local["radial_convergence_hydrostatic_equiv_mm"] = radial_convergence_m * 1000.0
            local["diametral_convergence_hydrostatic_equiv_mm"] = 2.0 * radial_convergence_m * 1000.0
            local["sidewall_single_convergence_estimate_mm"] = local[
                "radial_convergence_hydrostatic_equiv_mm"
            ]
            local["crown_settlement_estimate_mm"] = local[
                "radial_convergence_hydrostatic_equiv_mm"
            ]
            local["wall_convergence_estimate_mm"] = local[
                "diametral_convergence_hydrostatic_equiv_mm"
            ]
            local["crown_settlement_mm"] = local["crown_settlement_estimate_mm"]
            local["wall_convergence_mm"] = local["wall_convergence_estimate_mm"]
            local["sidewall_convergence_mm"] = local["wall_convergence_mm"]
            local["displacement_model"] = DISPLACEMENT_MODEL
            local["displacement_model_note"] = DISPLACEMENT_MODEL_NOTE
            for key, value in plastic.items():
                local[key] = value

            local["plastic_zone"] = local["plastic_zone_thickness_estimate_m"]
            local["notes"] = (
                "Stage 1 unsupported 2D plastic-zone-only screening. Settlement and wall "
                "convergence are disabled. Plastic-zone failure index uses generalized "
                "Hoek-Brown with D=0.5. tension/dilation are not used in Stage 1."
            )
            result_frames.append(local)

    return pd.concat(result_frames, ignore_index=True)


def add_hard_filter_and_score(
    all_results: pd.DataFrame,
    material_table: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """建立每個地層自己的 hard filter、score_2d，再彙整成全參數組排名。"""
    material_checks = []
    for (parameter_set_id, formation), group in material_table.groupby(["parameter_set_id", "formation"], sort=False):
        reasons = []
        row = group.iloc[0]
        if (group["E"] <= 0.0).any():
            reasons.append("E <= 0")
        if (group["cohesion"] < 0.0).any():
            reasons.append("cohesion < 0")
        if ((group["friction"] <= HARD_LIMITS["friction_min_deg"]) | (group["friction"] >= HARD_LIMITS["friction_max_deg"])).any():
            reasons.append("friction outside 0~60 deg")
        if ((group["poisson"] <= 0.0) | (group["poisson"] >= 0.5)).any():
            reasons.append("poisson <= 0 or >= 0.5")
        if (group["density"] <= 0.0).any():
            reasons.append("density <= 0")

        prior_positions = group[
            [
                "density_position_0_1",
                "E_position_0_1",
                "poisson_position_0_1",
                "cohesion_position_0_1",
                "friction_position_0_1",
            ]
        ].to_numpy(dtype=float)
        prior_penalty = float(np.nanmean((np.abs(prior_positions - 0.5) * 2.0) ** 2))
        material_checks.append(
            {
                "parameter_set_id": parameter_set_id,
                "formation": formation,
                "E_GPa": float(row["E_GPa"]),
                "cohesion_MPa": float(row["cohesion_MPa"]),
                "friction": float(row["friction"]),
                "sigma_ci_MPa": float(row["sigma_ci_MPa"]),
                "mi": float(row["mi"]),
                "GSI": float(row["GSI"]),
                "disturbance_D": float(row["disturbance_D"]),
                "hb_mb": float(row["hb_mb"]),
                "hb_s": float(row["hb_s"]),
                "hb_a": float(row["hb_a"]),
                "poisson": float(row["poisson"]),
                "density": float(row["density"]),
                "material_invalid_reason": "; ".join(reasons),
                "parameter_prior_penalty": prior_penalty,
            }
        )

    material_check_df = pd.DataFrame(material_checks)

    formation_rows = []
    segment_q = 0.95
    for (parameter_set_id, formation), group in all_results.groupby(["parameter_set_id", "formation"], sort=False):
        reasons = []
        finite_columns = [
            "plastic_zone_thickness_estimate_m",
            "plastic_zone_ratio_to_radius",
            "stability_index",
        ]
        for col in finite_columns:
            if not np.isfinite(group[col].to_numpy(dtype=float)).all():
                reasons.append(f"{col} has NaN/inf")

        max_plastic_ratio = float(group["plastic_zone_ratio_to_radius"].max())
        max_crown = np.nan
        max_wall = np.nan
        max_radial = np.nan
        max_diametral = np.nan
        max_plastic_thickness = float(group["plastic_zone_thickness_estimate_m"].max())
        max_stability_index = float(group["stability_index"].max())
        q95_crown = np.nan
        q95_wall = np.nan
        q95_radial = np.nan
        q95_diametral = np.nan
        q95_plastic_ratio = float(group["plastic_zone_ratio_to_radius"].quantile(segment_q))
        q95_plastic_thickness = float(group["plastic_zone_thickness_estimate_m"].quantile(segment_q))
        mean_crown = np.nan
        mean_wall = np.nan
        mean_plastic_ratio = float(group["plastic_zone_ratio_to_radius"].mean())
        mean_plastic_thickness = float(group["plastic_zone_thickness_estimate_m"].mean())
        danger = group.sort_values(
            ["plastic_zone_ratio_to_radius", "stability_index"],
            ascending=False,
        ).iloc[0]

        if q95_plastic_ratio > HARD_LIMITS["plastic_zone_ratio_to_radius"]:
            reasons.append("segment_p95_plastic_zone_ratio_to_radius too large")
        if (group["yield_state"] == "plastic_reaches_4a_estimate").any():
            reasons.append("plastic zone reaches 4a check limit")

        formation_rows.append(
            {
                "parameter_set_id": parameter_set_id,
                "formation": formation,
                "parameter_level": group["parameter_level"].iloc[0],
                "n_segment_points": int(len(group)),
                "settlement_filter_metric": "segment_p95",
                "plastic_zone_filter_metric": "segment_p95",
                "segment_p95_crown_settlement_mm": q95_crown,
                "segment_p95_wall_convergence_mm": q95_wall,
                "segment_p95_radial_convergence_hydrostatic_equiv_mm": q95_radial,
                "segment_p95_diametral_convergence_hydrostatic_equiv_mm": q95_diametral,
                "segment_p95_plastic_zone_thickness_estimate_m": q95_plastic_thickness,
                "segment_p95_plastic_zone_ratio_to_radius": q95_plastic_ratio,
                "mean_crown_settlement_mm": mean_crown,
                "mean_wall_convergence_mm": mean_wall,
                "mean_plastic_zone_thickness_estimate_m": mean_plastic_thickness,
                "mean_plastic_zone_ratio_to_radius": mean_plastic_ratio,
                "max_crown_settlement_mm": max_crown,
                "max_wall_convergence_mm": max_wall,
                "max_sidewall_convergence_mm": max_wall,
                "max_radial_convergence_hydrostatic_equiv_mm": max_radial,
                "max_diametral_convergence_hydrostatic_equiv_mm": max_diametral,
                "max_plastic_zone_thickness_estimate_m": max_plastic_thickness,
                "max_plastic_zone_ratio_to_radius": max_plastic_ratio,
                "max_stability_index": max_stability_index,
                "displacement_model": DISPLACEMENT_MODEL,
                "danger_mileage": float(danger["Mileage"]),
                "danger_formation": danger["formation_used"],
                "yield_state_control": danger["yield_state"],
                "result_invalid_reason": "; ".join(reasons),
            }
        )

    formation_summary = pd.DataFrame(formation_rows)
    formation_summary = formation_summary.merge(
        material_check_df,
        on=["parameter_set_id", "formation"],
        how="left",
    )

    reject_reasons = []
    for _, row in formation_summary.iterrows():
        reasons = []
        for col in ["material_invalid_reason", "result_invalid_reason"]:
            text = str(row.get(col, "")).strip()
            if text and text.lower() != "nan":
                reasons.append(text)
        reject_reasons.append("; ".join(reasons))

    formation_summary["reject_reason_formation"] = reject_reasons
    formation_summary["failure_flag_formation"] = (
        formation_summary["reject_reason_formation"].astype(str).str.len() > 0
    )
    formation_summary["pass_stage1_formation"] = ~formation_summary["failure_flag_formation"]

    formation_summary["plastic_zone_penalty"] = (
        formation_summary["segment_p95_plastic_zone_ratio_to_radius"]
        / HARD_LIMITS["plastic_zone_ratio_to_radius"]
    )
    formation_summary["crown_settlement_penalty"] = np.nan
    formation_summary["wall_convergence_penalty"] = np.nan
    formation_summary["convergence_penalty"] = 0.0
    formation_summary["stability_penalty"] = np.log1p(
        np.maximum(formation_summary["max_stability_index"], 0.0)
    )

    formation_summary["score_2d_formation"] = (
        0.75 * formation_summary["plastic_zone_penalty"]
        + 0.20 * formation_summary["stability_penalty"]
        + 0.05 * formation_summary["parameter_prior_penalty"]
    )
    formation_summary["rank_2d_formation"] = np.nan
    for formation, group in formation_summary.groupby("formation"):
        order = group.sort_values(
            ["score_2d_formation", "segment_p95_plastic_zone_ratio_to_radius", "max_stability_index"]
        )
        formation_summary.loc[order.index, "rank_2d_formation"] = np.arange(1, len(order) + 1)

    candidate_rows = []
    for parameter_set_id, group in formation_summary.groupby("parameter_set_id", sort=False):
        pass_stage1 = bool(group["pass_stage1_formation"].all())
        failed = group.loc[~group["pass_stage1_formation"], "formation"].astype(str).tolist()
        valid_scores = group["score_2d_formation"].replace([np.inf, -np.inf], np.nan)
        score = float(valid_scores.max())
        danger = group.sort_values(
            ["pass_stage1_formation", "score_2d_formation", "segment_p95_plastic_zone_ratio_to_radius"],
            ascending=[True, False, False],
        ).iloc[0]
        candidate_rows.append(
            {
                "parameter_set_id": parameter_set_id,
                "parameter_level": group["parameter_level"].iloc[0],
                "n_formations_checked": int(len(group)),
                "n_formations_passed": int(group["pass_stage1_formation"].sum()),
                "failed_formations": "; ".join(failed),
                "max_segment_p95_crown_settlement_mm": float(group["segment_p95_crown_settlement_mm"].max()),
                "max_segment_p95_wall_convergence_mm": float(group["segment_p95_wall_convergence_mm"].max()),
                "max_segment_p95_plastic_zone_thickness_estimate_m": float(group["segment_p95_plastic_zone_thickness_estimate_m"].max()),
                "max_segment_p95_plastic_zone_ratio_to_radius": float(group["segment_p95_plastic_zone_ratio_to_radius"].max()),
                "max_crown_settlement_mm": float(group["max_crown_settlement_mm"].max()),
                "max_wall_convergence_mm": float(group["max_wall_convergence_mm"].max()),
                "max_sidewall_convergence_mm": float(group["max_wall_convergence_mm"].max()),
                "max_radial_convergence_hydrostatic_equiv_mm": float(group["max_radial_convergence_hydrostatic_equiv_mm"].max()),
                "max_diametral_convergence_hydrostatic_equiv_mm": float(group["max_diametral_convergence_hydrostatic_equiv_mm"].max()),
                "max_plastic_zone_thickness_estimate_m": float(group["max_plastic_zone_thickness_estimate_m"].max()),
                "max_plastic_zone_ratio_to_radius": float(group["max_plastic_zone_ratio_to_radius"].max()),
                "max_stability_index": float(group["max_stability_index"].max()),
                "displacement_model": DISPLACEMENT_MODEL,
                "danger_mileage": float(danger["danger_mileage"]),
                "danger_formation": danger["formation"],
                "yield_state_control": danger["yield_state_control"],
                "material_invalid_reason": "; ".join(
                    sorted(set(filter(None, group["material_invalid_reason"].fillna("").astype(str))))
                ),
                "result_invalid_reason": "; ".join(
                    sorted(set(filter(None, group["result_invalid_reason"].fillna("").astype(str))))
                ),
                "parameter_prior_penalty": float(group["parameter_prior_penalty"].mean()),
                "plastic_zone_penalty": float(group["plastic_zone_penalty"].max()),
                "crown_settlement_penalty": float(group["crown_settlement_penalty"].max()),
                "wall_convergence_penalty": float(group["wall_convergence_penalty"].max()),
                "convergence_penalty": float(group["convergence_penalty"].max()),
                "stability_penalty": float(group["stability_penalty"].max()),
                "score_2d": score,
                "failure_flag": not pass_stage1,
                "pass_stage1": pass_stage1,
                "reject_reason": "; ".join(
                    f"{row.formation}: {row.reject_reason_formation}"
                    for row in group.itertuples()
                    if str(row.reject_reason_formation)
                ),
            }
        )

    candidate_summary = pd.DataFrame(candidate_rows)
    ranked_order = candidate_summary.sort_values(
        ["score_2d", "max_segment_p95_plastic_zone_ratio_to_radius", "max_stability_index"]
    )
    candidate_summary["rank_2d"] = np.nan
    if not ranked_order.empty:
        candidate_summary.loc[ranked_order.index, "rank_2d"] = np.arange(1, len(ranked_order) + 1)

    candidate_summary = candidate_summary.sort_values(
        ["pass_stage1", "score_2d"],
        ascending=[False, True],
    ).reset_index(drop=True)

    formation_merge_cols = [
        "parameter_set_id",
        "formation",
        "failure_flag_formation",
        "pass_stage1_formation",
        "reject_reason_formation",
        "score_2d_formation",
        "rank_2d_formation",
        "settlement_filter_metric",
        "plastic_zone_filter_metric",
        "segment_p95_crown_settlement_mm",
        "segment_p95_wall_convergence_mm",
        "segment_p95_plastic_zone_thickness_estimate_m",
        "segment_p95_plastic_zone_ratio_to_radius",
    ]
    all_results = all_results.merge(
        formation_summary[formation_merge_cols],
        on=["parameter_set_id", "formation"],
        how="left",
    )
    candidate_merge_cols = [
        "parameter_set_id",
        "failure_flag",
        "pass_stage1",
        "reject_reason",
        "score_2d",
        "rank_2d",
    ]
    all_results = all_results.merge(candidate_summary[candidate_merge_cols], on="parameter_set_id", how="left")

    return all_results, candidate_summary, formation_summary


def build_all_candidate_results(
    material_table: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    formation_summary: pd.DataFrame,
) -> pd.DataFrame:
    """輸出所有候選參數組合，每列是一個 parameter_set_id x formation。"""
    cols_from_candidate = [
        "parameter_set_id",
        "failed_formations",
        "reject_reason",
        "failure_flag",
        "pass_stage1",
        "score_2d",
        "rank_2d",
    ]
    cols_from_formation = [
        "parameter_set_id",
        "formation",
        "n_segment_points",
        "settlement_filter_metric",
        "plastic_zone_filter_metric",
        "segment_p95_crown_settlement_mm",
        "segment_p95_wall_convergence_mm",
        "segment_p95_radial_convergence_hydrostatic_equiv_mm",
        "segment_p95_diametral_convergence_hydrostatic_equiv_mm",
        "segment_p95_plastic_zone_thickness_estimate_m",
        "segment_p95_plastic_zone_ratio_to_radius",
        "mean_crown_settlement_mm",
        "mean_wall_convergence_mm",
        "mean_plastic_zone_thickness_estimate_m",
        "mean_plastic_zone_ratio_to_radius",
        "max_crown_settlement_mm",
        "max_wall_convergence_mm",
        "max_radial_convergence_hydrostatic_equiv_mm",
        "max_diametral_convergence_hydrostatic_equiv_mm",
        "max_plastic_zone_thickness_estimate_m",
        "max_plastic_zone_ratio_to_radius",
        "max_stability_index",
        "displacement_model",
        "danger_mileage",
        "danger_formation",
        "yield_state_control",
        "reject_reason_formation",
        "failure_flag_formation",
        "pass_stage1_formation",
        "plastic_zone_penalty",
        "crown_settlement_penalty",
        "wall_convergence_penalty",
        "convergence_penalty",
        "parameter_prior_penalty",
        "stability_penalty",
        "score_2d_formation",
        "rank_2d_formation",
    ]
    all_candidate_results = material_table.merge(
        formation_summary[cols_from_formation],
        on=["parameter_set_id", "formation"],
        how="left",
    ).merge(
        candidate_summary[cols_from_candidate],
        on="parameter_set_id",
        how="left",
    )
    all_candidate_results["rock_class"] = all_candidate_results["formation"]
    all_candidate_results["plastic_zone"] = all_candidate_results[
        "segment_p95_plastic_zone_thickness_estimate_m"
    ]
    all_candidate_results["plastic_radius_estimate_m"] = (
        a + all_candidate_results["segment_p95_plastic_zone_thickness_estimate_m"]
    )
    all_candidate_results["crown_settlement_mm"] = all_candidate_results[
        "segment_p95_crown_settlement_mm"
    ]
    all_candidate_results["wall_convergence_mm"] = all_candidate_results[
        "segment_p95_wall_convergence_mm"
    ]
    all_candidate_results["radial_convergence_hydrostatic_equiv_mm"] = all_candidate_results[
        "segment_p95_radial_convergence_hydrostatic_equiv_mm"
    ]
    all_candidate_results["diametral_convergence_hydrostatic_equiv_mm"] = all_candidate_results[
        "segment_p95_diametral_convergence_hydrostatic_equiv_mm"
    ]
    all_candidate_results["stability_index"] = all_candidate_results[
        "max_stability_index"
    ]
    all_candidate_results["failure_criterion"] = FAILURE_CRITERION
    all_candidate_results["notes"] = (
        "All-results row format: one parameter_set_id x formation row; main metrics are segment_p95 values within that formation. "
        "Displacement is CCM hydrostatic-equivalent estimate, not directional K0 crown/wall solution."
    )

    stable_columns = [
        "parameter_set_id",
        "formation",
        "rock_class",
        "material_group",
        "used_in_stage1_geometry",
        "parameter_level",
        "E",
        "E_GPa",
        "cohesion",
        "cohesion_MPa",
        "friction",
        "sigma_ci",
        "sigma_ci_MPa",
        "mi",
        "GSI",
        "disturbance_D",
        "hb_mb",
        "hb_s",
        "hb_a",
        "tension",
        "poisson",
        "density",
        "dilation",
        "plastic_zone",
        "plastic_radius_estimate_m",
        "settlement_filter_metric",
        "plastic_zone_filter_metric",
        "n_segment_points",
        "segment_p95_crown_settlement_mm",
        "segment_p95_wall_convergence_mm",
        "segment_p95_plastic_zone_thickness_estimate_m",
        "segment_p95_plastic_zone_ratio_to_radius",
        "mean_crown_settlement_mm",
        "mean_wall_convergence_mm",
        "mean_plastic_zone_thickness_estimate_m",
        "mean_plastic_zone_ratio_to_radius",
        "max_plastic_zone_thickness_estimate_m",
        "max_plastic_zone_ratio_to_radius",
        "crown_settlement_mm",
        "wall_convergence_mm",
        "radial_convergence_hydrostatic_equiv_mm",
        "diametral_convergence_hydrostatic_equiv_mm",
        "displacement_model",
        "failure_criterion",
        "stability_index",
        "yield_state_control",
        "failure_flag_formation",
        "pass_stage1_formation",
        "reject_reason_formation",
        "score_2d_formation",
        "rank_2d_formation",
        "failure_flag",
        "score_2d",
        "rank_2d",
        "pass_stage1",
        "reject_reason",
        "failed_formations",
        "danger_mileage",
        "danger_formation",
        "plastic_zone_penalty",
        "crown_settlement_penalty",
        "wall_convergence_penalty",
        "convergence_penalty",
        "parameter_prior_penalty",
        "stability_penalty",
        "notes",
    ]
    return all_candidate_results[stable_columns].sort_values(
        ["parameter_set_id", "formation"]
    ).reset_index(drop=True)


def build_passed_for_stage2(
    material_table: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    formation_summary: pd.DataFrame,
) -> pd.DataFrame:
    """輸出給 Stage 2 FLAC3D 小模型使用的乾淨材料表。"""
    passed_summary = candidate_summary[candidate_summary["pass_stage1"]].copy()
    if passed_summary.empty:
        return pd.DataFrame(
            columns=[
                "parameter_set_id",
                "rank_2d",
                "formation",
                "material_group",
                "used_in_stage1_geometry",
                "parameter_level",
                "E",
                "E_GPa",
                "cohesion",
                "cohesion_MPa",
                "friction",
                "sigma_ci",
                "sigma_ci_MPa",
                "mi",
                "GSI",
                "disturbance_D",
                "hb_mb",
                "hb_s",
                "hb_a",
                "tension",
                "poisson",
                "density",
                "dilation",
                "score_2d",
                "max_crown_settlement_mm",
                "max_wall_convergence_mm",
                "max_radial_convergence_hydrostatic_equiv_mm",
                "max_diametral_convergence_hydrostatic_equiv_mm",
                "displacement_model",
                "selected_for_stage2_recommendation",
                "notes",
            ]
        )

    stage2_count = min(RECOMMENDED_STAGE2_COUNT, len(passed_summary))
    passed_summary["selected_for_stage2_recommendation"] = (
        passed_summary["rank_2d"] <= stage2_count
    )

    cols_from_summary = [
        "parameter_set_id",
        "rank_2d",
        "score_2d",
        "failed_formations",
        "max_crown_settlement_mm",
        "max_wall_convergence_mm",
        "max_segment_p95_crown_settlement_mm",
        "max_segment_p95_wall_convergence_mm",
        "max_radial_convergence_hydrostatic_equiv_mm",
        "max_diametral_convergence_hydrostatic_equiv_mm",
        "max_plastic_zone_thickness_estimate_m",
        "max_plastic_zone_ratio_to_radius",
        "max_stability_index",
        "displacement_model",
        "danger_mileage",
        "danger_formation",
        "selected_for_stage2_recommendation",
    ]
    cols_from_formation = [
        "parameter_set_id",
        "formation",
        "pass_stage1_formation",
        "rank_2d_formation",
        "score_2d_formation",
        "segment_p95_crown_settlement_mm",
        "segment_p95_wall_convergence_mm",
        "segment_p95_plastic_zone_thickness_estimate_m",
        "segment_p95_plastic_zone_ratio_to_radius",
        "reject_reason_formation",
    ]
    passed_for_stage2 = material_table.merge(
        passed_summary[cols_from_summary],
        on="parameter_set_id",
        how="inner",
    ).merge(
        formation_summary[cols_from_formation],
        on=["parameter_set_id", "formation"],
        how="left",
    )
    passed_for_stage2 = passed_for_stage2.sort_values(["rank_2d", "formation"]).reset_index(drop=True)
    passed_for_stage2["failure_criterion"] = FAILURE_CRITERION
    passed_for_stage2["notes"] = (
        "Stage 2 row format: one parameter_set_id x formation row; unsupported excavation; "
        "read by parameter_set_id group. Stage 1 displacement columns are hydrostatic-equivalent "
        "screening estimates only."
    )

    stable_columns = [
        "parameter_set_id",
        "rank_2d",
        "formation",
        "material_group",
        "used_in_stage1_geometry",
        "parameter_level",
        "E",
        "E_GPa",
        "cohesion",
        "cohesion_MPa",
        "friction",
        "sigma_ci",
        "sigma_ci_MPa",
        "mi",
        "GSI",
        "disturbance_D",
        "hb_mb",
        "hb_s",
        "hb_a",
        "tension",
        "poisson",
        "density",
        "dilation",
        "score_2d",
        "score_2d_formation",
        "rank_2d_formation",
        "max_crown_settlement_mm",
        "max_wall_convergence_mm",
        "max_segment_p95_crown_settlement_mm",
        "max_segment_p95_wall_convergence_mm",
        "segment_p95_crown_settlement_mm",
        "segment_p95_wall_convergence_mm",
        "segment_p95_plastic_zone_thickness_estimate_m",
        "segment_p95_plastic_zone_ratio_to_radius",
        "max_radial_convergence_hydrostatic_equiv_mm",
        "max_diametral_convergence_hydrostatic_equiv_mm",
        "displacement_model",
        "failure_criterion",
        "max_plastic_zone_thickness_estimate_m",
        "max_plastic_zone_ratio_to_radius",
        "max_stability_index",
        "danger_mileage",
        "danger_formation",
        "selected_for_stage2_recommendation",
        "pass_stage1_formation",
        "reject_reason_formation",
        "failed_formations",
        "notes",
    ]
    return passed_for_stage2[stable_columns]


def build_screened_parameter_ranges(
    material_table: pd.DataFrame,
    formation_summary: pd.DataFrame,
) -> pd.DataFrame:
    """彙整各地層篩選前與篩選後的參數 min/max。"""
    parameters = [
        ("E_GPa", "GPa"),
        ("cohesion_MPa", "MPa"),
        ("friction", "deg"),
        ("sigma_ci_MPa", "MPa"),
        ("mi", "-"),
        ("GSI", "-"),
        ("disturbance_D", "-"),
        ("density", "kg/m3"),
        ("poisson", "-"),
    ]
    material_with_pass = material_table.merge(
        formation_summary[
            ["parameter_set_id", "formation", "pass_stage1_formation", "score_2d_formation"]
        ],
        on=["parameter_set_id", "formation"],
        how="left",
    )
    rows = []
    for formation, group in material_with_pass.groupby("formation", sort=False):
        pass_mask = group["pass_stage1_formation"].eq(True)
        passed = group[pass_mask].copy()
        for parameter, unit in parameters:
            input_values = group[parameter].to_numpy(dtype=float)
            screened_values = passed[parameter].to_numpy(dtype=float) if not passed.empty else np.array([])
            rows.append(
                {
                    "formation": formation,
                    "parameter": parameter,
                    "unit": unit,
                    "input_count": int(np.isfinite(input_values).sum()),
                    "input_min": float(np.nanmin(input_values)),
                    "input_max": float(np.nanmax(input_values)),
                    "screened_count": int(np.isfinite(screened_values).sum()),
                    "screened_min": float(np.nanmin(screened_values)) if len(screened_values) else np.nan,
                    "screened_max": float(np.nanmax(screened_values)) if len(screened_values) else np.nan,
                    "screened_pass_ratio": float(len(screened_values) / len(input_values)) if len(input_values) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def write_stage1_figures(
    candidate_summary: pd.DataFrame,
    formation_summary: pd.DataFrame,
    passed_for_stage2: pd.DataFrame,
    screened_parameter_ranges: pd.DataFrame,
) -> dict[str, str]:
    """輸出 Stage 1 快篩對比圖。"""
    if plt is None:
        return {}

    figure_paths = {}
    plot_data = candidate_summary.copy()
    plot_data["plot_score_2d"] = plot_data["score_2d"].replace([np.inf, -np.inf], np.nan)
    plot_data = plot_data.sort_values(["pass_stage1", "plot_score_2d"], ascending=[False, True]).reset_index(drop=True)
    plot_data["plot_index"] = np.arange(1, len(plot_data) + 1)
    passed = plot_data[plot_data["pass_stage1"]].copy()

    colors = np.where(plot_data["pass_stage1"], "#2ca25f", "#de2d26")

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.bar(plot_data["plot_index"], plot_data["plot_score_2d"], color=colors, width=0.85)
    ax.set_xlabel("候選參數組排序")
    ax.set_ylabel("score_2d（越小越好）")
    ax.set_title("Stage 1 score_2d 排名與通過狀態")
    ax.grid(axis="y", alpha=0.25)
    ax.text(0.99, 0.95, "綠色=通過；紅色=淘汰", transform=ax.transAxes, ha="right", va="top")
    path = figure_dir / "stage1_2d_score_ranking.png"
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    figure_paths["score_ranking_png"] = str(path)

    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8), gridspec_kw={"width_ratios": [1.0, 2.4]})
    pass_counts = plot_data["pass_stage1"].map({True: "通過", False: "淘汰"}).value_counts().reindex(["通過", "淘汰"]).fillna(0)
    axes[0].bar(pass_counts.index, pass_counts.values, color=["#2ca25f", "#de2d26"])
    axes[0].set_title("hard filter 結果")
    axes[0].set_ylabel("參數組數量")
    axes[0].grid(axis="y", alpha=0.25)

    reason_counts = (
        plot_data.loc[~plot_data["pass_stage1"], "reject_reason"]
        .replace("", "未標示")
        .value_counts()
        .head(8)
    )
    axes[1].barh(reason_counts.index[::-1], reason_counts.values[::-1], color="#756bb1")
    axes[1].set_title("主要淘汰原因")
    axes[1].set_xlabel("參數組數量")
    axes[1].grid(axis="x", alpha=0.25)
    path = figure_dir / "stage1_2d_filter_summary.png"
    fig.subplots_adjust(left=0.07, right=0.98, wspace=0.45)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    figure_paths["filter_summary_png"] = str(path)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(
        plot_data["score_2d"].replace([np.inf, -np.inf], np.nan),
        plot_data["max_segment_p95_plastic_zone_thickness_estimate_m"],
        c=np.where(plot_data["pass_stage1"], "#2ca25f", "#de2d26"),
        edgecolor="black",
        linewidth=0.35,
        s=55,
        alpha=0.85,
    )
    ax.axhline(
        HARD_LIMITS["plastic_zone_ratio_to_radius"] * a,
        color="#756bb1",
        linestyle="--",
        linewidth=1.2,
        label="plastic hard limit",
    )
    ax.set_xlabel("score_2d (plastic-zone-only)")
    ax.set_ylabel("segment P95 plastic-zone thickness (m)")
    ax.set_title("Stage 1 plastic-zone-only screening")
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    path = figure_dir / "stage1_2d_plastic_zone_score.png"
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    figure_paths["plastic_zone_score_png"] = str(path)

    return figure_paths

    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(
        plot_data["max_segment_p95_wall_convergence_mm"],
        plot_data["max_segment_p95_plastic_zone_thickness_estimate_m"],
        c=np.where(plot_data["pass_stage1"], 1, 0),
        cmap="RdYlGn",
        edgecolor="black",
        linewidth=0.35,
        s=55,
        alpha=0.85,
    )
    ax.axvline(HARD_LIMITS["wall_convergence_mm"], color="#de2d26", linestyle="--", linewidth=1.2, label="wall hard limit")
    ax.axhline(HARD_LIMITS["plastic_zone_ratio_to_radius"] * a, color="#756bb1", linestyle="--", linewidth=1.2, label="plastic hard limit")
    ax.set_xlabel("各地層 segment P95 側壁總收斂最大值（mm；CCM 靜水等效）")
    ax.set_ylabel("各地層 segment P95 塑性區厚度最大值（m）")
    ax.set_title("位移與塑性區對比（以各地層 segment P95 篩選）")
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    path = figure_dir / "stage1_2d_displacement_vs_plastic_zone.png"
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    figure_paths["displacement_vs_plastic_zone_png"] = str(path)

    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    ax.scatter(
        plot_data["max_segment_p95_crown_settlement_mm"],
        plot_data["max_segment_p95_wall_convergence_mm"],
        c=np.where(plot_data["pass_stage1"], "#2ca25f", "#de2d26"),
        edgecolor="black",
        linewidth=0.35,
        s=55,
        alpha=0.85,
    )
    limit_x = float(np.nanmax(plot_data["max_segment_p95_crown_settlement_mm"].to_numpy(dtype=float)))
    x_line = np.linspace(0.0, max(limit_x, 1.0), 100)
    ax.plot(x_line, 2.0 * x_line, color="#08519c", linewidth=1.5, label="wall = 2 × crown")
    ax.set_xlabel("各地層 segment P95 頂拱沉陷最大值（mm；CCM 靜水等效）")
    ax.set_ylabel("各地層 segment P95 側壁總收斂最大值（mm；CCM 靜水等效）")
    ax.set_title("頂拱/側壁位移公式檢查")
    ax.text(
        0.03,
        0.97,
        "目前 crown 與 wall 不是獨立方向性解\nK0=1.2 時僅作快速篩選指標",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
    )
    ax.grid(alpha=0.25)
    ax.legend(loc="lower right")
    path = figure_dir / "stage1_2d_displacement_formula_check.png"
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    figure_paths["displacement_formula_check_png"] = str(path)

    top = passed.sort_values("rank_2d").head(RECOMMENDED_STAGE2_COUNT)
    fig, ax1 = plt.subplots(figsize=(12, 5.8))
    x = np.arange(len(top))
    labels = top["parameter_set_id"].astype(str).to_numpy()
    ax1.bar(x, top["score_2d"], color="#3182bd", alpha=0.85, label="score_2d")
    ax1.set_ylabel("score_2d（越小越好）")
    ax1.set_xlabel("建議進 Stage 2 的參數組")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=60, ha="right")
    ax1.grid(axis="y", alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(x, top["max_segment_p95_crown_settlement_mm"], color="#e6550d", marker="o", linewidth=1.6, label="頂拱 P95")
    ax2.plot(x, top["max_segment_p95_wall_convergence_mm"], color="#31a354", marker="s", linewidth=1.6, label="側壁總收斂 P95")
    ax2.set_ylabel("位移估算值（mm；CCM 靜水等效）")
    ax1.set_title("Stage 2 建議候選參數前 20 組")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
    path = figure_dir / "stage1_2d_top20_stage2_candidates.png"
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    figure_paths["top20_stage2_candidates_png"] = str(path)

    if not passed_for_stage2.empty:
        top_ids = top["parameter_set_id"].astype(str).tolist()
        mat = passed_for_stage2[passed_for_stage2["parameter_set_id"].isin(top_ids)].copy()
        mat["parameter_set_id"] = pd.Categorical(mat["parameter_set_id"], categories=top_ids, ordered=True)
        pivot = mat.pivot_table(
            index="parameter_set_id",
            columns="formation",
            values="E_GPa",
            aggfunc="first",
            observed=False,
        )
        fig, ax = plt.subplots(figsize=(12, 6))
        im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="viridis")
        ax.set_xticks(np.arange(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns, rotation=35, ha="right")
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels(pivot.index.astype(str))
        ax.set_title("前 20 組候選參數的 E 分布（GPa）")
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("E（GPa）")
        path = figure_dir / "stage1_2d_top20_E_heatmap.png"
        fig.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)
        figure_paths["top20_E_heatmap_png"] = str(path)

    if not screened_parameter_ranges.empty:
        formation_order = ["SS_NK", "Interbedded_ST", "SH_ST", "SS_NC", "Fault"]
        parameter_order = ["E_GPa", "cohesion_MPa", "friction", "density", "poisson"]
        fig, axes = plt.subplots(len(parameter_order), 1, figsize=(11, 13), sharey=False)
        colors_range = {"input": "#9e9ac8", "screened": "#2ca25f"}
        for ax, parameter in zip(axes, parameter_order):
            sub = screened_parameter_ranges[screened_parameter_ranges["parameter"] == parameter]
            table = sub.set_index("formation")
            y_base = np.arange(len(formation_order))
            for y_index, formation in enumerate(formation_order):
                if formation not in table.index:
                    continue
                row = table.loc[formation]
                ax.hlines(y_index - 0.14, row["input_min"], row["input_max"], color=colors_range["input"], linewidth=3)
                if np.isfinite(row["screened_min"]) and np.isfinite(row["screened_max"]):
                    ax.hlines(y_index + 0.14, row["screened_min"], row["screened_max"], color=colors_range["screened"], linewidth=3)
                    ax.plot([row["screened_min"], row["screened_max"]], [y_index + 0.14, y_index + 0.14], "o", color=colors_range["screened"], markersize=4)
                ax.plot([row["input_min"], row["input_max"]], [y_index - 0.14, y_index - 0.14], "o", color=colors_range["input"], markersize=4)
            unit = sub["unit"].dropna().iloc[0] if not sub.empty else ""
            ax.set_yticks(y_base)
            ax.set_yticklabels(formation_order)
            ax.set_xlabel(f"{parameter} ({unit})")
            ax.set_title(f"{parameter}：原始 min-max 與篩選後 min-max")
            ax.grid(axis="x", alpha=0.25)
        axes[0].legend(
            handles=[
                plt.Line2D([0], [0], color=colors_range["input"], lw=3, marker="o", label="原始區間"),
                plt.Line2D([0], [0], color=colors_range["screened"], lw=3, marker="o", label="篩選後區間"),
            ],
            loc="best",
        )
        fig.suptitle("各地層參數篩選前後 min-max", fontsize=15)
        path = figure_dir / "stage1_formation_parameter_screening_ranges.png"
        fig.tight_layout(rect=[0, 0, 1, 0.98])
        fig.savefig(path, dpi=200)
        plt.close(fig)
        figure_paths["formation_parameter_screening_ranges_png"] = str(path)

    return figure_paths


geometry = read_geometry()
stats = read_material_statistics()
material_table = build_candidate_material_table(geometry, stats)
all_results = run_stage1_screening(geometry, material_table)
all_results, candidate_summary, formation_summary = add_hard_filter_and_score(all_results, material_table)
screened_parameter_ranges = build_screened_parameter_ranges(material_table, formation_summary)
all_candidate_results = build_all_candidate_results(material_table, candidate_summary, formation_summary)
passed_for_stage2 = build_passed_for_stage2(material_table, candidate_summary, formation_summary)
figure_outputs = write_stage1_figures(candidate_summary, formation_summary, passed_for_stage2, screened_parameter_ranges)

all_results_csv = output_dir / "stage1_2d_screening_all_results.csv"
detailed_by_mileage_csv = output_dir / "stage1_2d_screening_detailed_by_mileage.csv"
passed_for_stage2_csv = output_dir / "stage1_2d_screening_passed_for_stage2.csv"
candidate_summary_csv = output_dir / "stage1_2d_screening_candidate_summary.csv"
formation_summary_csv = output_dir / "stage1_2d_screening_formation_summary.csv"
screened_parameter_ranges_csv = output_dir / "stage1_formation_screened_parameter_ranges.csv"
material_table_csv = output_dir / "stage1_2d_screening_material_table.csv"
summary_json = output_dir / "stage1_2d_screening_summary.json"
summary_md = output_dir / "stage1_2d_screening_summary.md"

legacy_results_csv = output_dir / "01_2d_plane_screening_results.csv"
legacy_case_summary_csv = output_dir / "01_2d_plane_screening_case_summary.csv"
legacy_flac3d_cases_csv = output_dir / "01_2d_plane_screening_flac3d_representative_cases.csv"
legacy_material_levels_csv = output_dir / "01_material_parameter_levels.csv"
legacy_state_json = output_dir / "01_2d_plane_screening_state.json"
legacy_summary_json = output_dir / "01_2d_plane_screening_summary.json"

all_candidate_results.to_csv(all_results_csv, index=False, encoding="utf-8-sig")
passed_for_stage2.to_csv(passed_for_stage2_csv, index=False, encoding="utf-8-sig")
candidate_summary.to_csv(candidate_summary_csv, index=False, encoding="utf-8-sig")
formation_summary.to_csv(formation_summary_csv, index=False, encoding="utf-8-sig")
screened_parameter_ranges.to_csv(screened_parameter_ranges_csv, index=False, encoding="utf-8-sig")
material_table.to_csv(material_table_csv, index=False, encoding="utf-8-sig")

# 保留舊檔名，讓後續既有讀檔流程不會斷掉；內容已改為 Stage 1 無支撐候選參數總表。
all_candidate_results.to_csv(legacy_results_csv, index=False, encoding="utf-8-sig")
candidate_summary.to_csv(legacy_case_summary_csv, index=False, encoding="utf-8-sig")
passed_for_stage2.to_csv(legacy_flac3d_cases_csv, index=False, encoding="utf-8-sig")
material_table.to_csv(legacy_material_levels_csv, index=False, encoding="utf-8-sig")

if WRITE_DETAILED_BY_MILEAGE:
    all_results.to_csv(detailed_by_mileage_csv, index=False, encoding="utf-8-sig")

recommended_stage2_count = int(passed_for_stage2["parameter_set_id"].nunique()) if not passed_for_stage2.empty else 0
recommended_stage2_count = min(RECOMMENDED_STAGE2_COUNT, recommended_stage2_count)

control_formation_counts = (
    candidate_summary[candidate_summary["pass_stage1"]]["danger_formation"]
    .value_counts()
    .to_dict()
)
passed_rows_by_formation = (
    passed_for_stage2["formation"].value_counts().to_dict()
    if not passed_for_stage2.empty
    else {}
)

summary = {
    "workflow": WORKFLOW_NAME,
    "notebook": "01_2d_plane_screening.ipynb",
    "material_stats_csv": str(material_stats_csv),
    "geometry_base_csv": str(geometry_base_csv),
    "output_dir": str(output_dir),
    "B_m": B,
    "D_m": D,
    "radius_m": a,
    "K0": K0,
    "support_assumption": "unsupported; no shotcrete; no equivalent support",
    "screening_mode": SCREENING_MODE,
    "failure_criterion": FAILURE_CRITERION,
    "hoek_brown": {
        "D": HB_DISTURBANCE_D,
        "mb": "mi * exp((GSI - 100) / (28 - 14D))",
        "s": "exp((GSI - 100) / (9 - 3D))",
        "a": "0.5 + (exp(-GSI/15) - exp(-20/3)) / 6",
    },
    "displacement_model": {
        "name": DISPLACEMENT_MODEL,
        "formula": None,
        "crown_settlement_mm": "disabled",
        "wall_convergence_mm": "disabled",
        "limitation": "Settlement/convergence are not used for filtering or ranking in plastic-zone-only mode.",
    },
    "n_parameter_sets": int(candidate_summary["parameter_set_id"].nunique()),
    "n_material_rows": int(len(material_table)),
    "n_geometry_rows": int(len(geometry)),
    "n_all_candidate_result_rows": int(len(all_candidate_results)),
    "n_formation_summary_rows": int(len(formation_summary)),
    "n_detailed_by_mileage_rows": int(len(all_results)),
    "write_detailed_by_mileage": bool(WRITE_DETAILED_BY_MILEAGE),
    "n_hard_filter_rejected": int((~candidate_summary["pass_stage1"]).sum()),
    "n_pass_stage1": int(candidate_summary["pass_stage1"].sum()),
    "n_formation_hard_filter_rejected": int((~formation_summary["pass_stage1_formation"]).sum()),
    "n_formation_pass_stage1": int(formation_summary["pass_stage1_formation"].sum()),
    "recommended_stage2_parameter_sets": recommended_stage2_count,
    "hard_limits": HARD_LIMITS,
    "plastic_zone_estimate": {
        "radius_limit_factor": PLASTIC_RADIUS_LIMIT_FACTOR,
        "radius_samples": PLASTIC_RADIUS_SAMPLES,
        "theta_samples": PLASTIC_THETA_SAMPLES,
        "index_scale": PLASTIC_ZONE_INDEX_SCALE,
        "note": "Kirsch tunnel-boundary Mohr-Coulomb index converted to plastic-zone estimate, not final FLAC3D result.",
    },
    "score_2d_definition": {
        "direction": "smaller_is_better",
        "formula": "formation score = 0.75*segment_p95_plastic_zone_penalty + 0.20*log1p(max_stability_index_positive) + 0.05*parameter_prior_penalty; candidate score = worst passed formation score",
        "note": "Only plastic-zone filters are applied by formation using segment P95. Settlement and wall convergence are disabled.",
    },
    "control_formation_counts_for_passed_sets": control_formation_counts,
    "passed_material_rows_by_formation": passed_rows_by_formation,
    "top_parameters": json.loads(
        candidate_summary[candidate_summary["pass_stage1"]]
        .sort_values("rank_2d")
        .head(RECOMMENDED_STAGE2_COUNT)
        .to_json(orient="records", force_ascii=False)
    ),
    "outputs": {
        "all_results_csv": str(all_results_csv),
        "detailed_by_mileage_csv": str(detailed_by_mileage_csv) if WRITE_DETAILED_BY_MILEAGE else None,
        "passed_for_stage2_csv": str(passed_for_stage2_csv),
        "candidate_summary_csv": str(candidate_summary_csv),
        "formation_summary_csv": str(formation_summary_csv),
        "screened_parameter_ranges_csv": str(screened_parameter_ranges_csv),
        "material_table_csv": str(material_table_csv),
        "figure_dir": str(figure_dir),
        "figures": figure_outputs,
        "summary_json": str(summary_json),
        "summary_md": str(summary_md),
        "legacy_results_csv": str(legacy_results_csv),
        "legacy_case_summary_csv": str(legacy_case_summary_csv),
        "legacy_flac3d_cases_csv": str(legacy_flac3d_cases_csv),
        "legacy_material_levels_csv": str(legacy_material_levels_csv),
    },
}

top10_for_md = candidate_summary.sort_values("rank_2d").head(10)
if top10_for_md.empty:
    top10_md = "No ranked parameter sets."
else:
    top10_lines = [
        "| parameter_set_id | rank_2d | score_2d | p95_plastic_zone_m | plastic_ratio | max_stability_index | danger_formation |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in top10_for_md.iterrows():
        top10_lines.append(
            "| {parameter_set_id} | {rank:.0f} | {score:.4f} | {plastic:.2f} | {ratio:.3f} | {stability:.2f} | {formation} |".format(
                parameter_set_id=row["parameter_set_id"],
                rank=float(row["rank_2d"]),
                score=float(row["score_2d"]),
                plastic=float(row["max_segment_p95_plastic_zone_thickness_estimate_m"]),
                ratio=float(row["max_segment_p95_plastic_zone_ratio_to_radius"]),
                stability=float(row["max_stability_index"]),
                formation=row["danger_formation"],
            )
        )
    top10_md = "\n".join(top10_lines)
figure_lines = "\n".join(f"- {name}: `{path}`" for name, path in figure_outputs.items())
summary_md_text = f"""# Stage 1 2D Screening Summary

## Run Summary
- Total candidate parameter sets: {summary["n_parameter_sets"]}
- Hard-filter rejected: {summary["n_hard_filter_rejected"]}
- Passed Stage 1: {summary["n_pass_stage1"]}
- Formation-level rejected rows: {summary["n_formation_hard_filter_rejected"]}
- Formation-level passed rows: {summary["n_formation_pass_stage1"]}
- Recommended Stage 2 parameter sets: {summary["recommended_stage2_parameter_sets"]}
- Support assumption: {summary["support_assumption"]}

## Formula Check
- Screening mode: `{SCREENING_MODE}`
- Failure criterion: `{FAILURE_CRITERION}`
- Hoek-Brown disturbance factor: `D = {HB_DISTURBANCE_D}`
- Settlement and wall convergence are disabled in this screening run.
- Plastic-zone filters are applied per formation using segment P95, not a single whole-tunnel maximum.
- `score_2d` is controlled by the worst passed formation score and uses only plastic-zone ratio, Hoek-Brown stability index, and parameter prior penalty.

## Top Ranked Parameter Sets
{top10_md}

## Figures
{figure_lines}
"""

summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
summary_md.write_text(summary_md_text, encoding="utf-8")
legacy_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
legacy_state_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

print("完成 Stage 1：2D 無支撐解析解快速篩選")
print(
    json.dumps(
        {
            "n_parameter_sets": summary["n_parameter_sets"],
            "n_all_candidate_result_rows": summary["n_all_candidate_result_rows"],
            "n_detailed_by_mileage_rows": summary["n_detailed_by_mileage_rows"],
            "n_hard_filter_rejected": summary["n_hard_filter_rejected"],
            "n_pass_stage1": summary["n_pass_stage1"],
            "n_formation_hard_filter_rejected": summary["n_formation_hard_filter_rejected"],
            "n_formation_pass_stage1": summary["n_formation_pass_stage1"],
            "recommended_stage2_parameter_sets": summary["recommended_stage2_parameter_sets"],
            "all_results_csv": str(all_results_csv),
            "passed_for_stage2_csv": str(passed_for_stage2_csv),
        },
        ensure_ascii=False,
        indent=2,
    )
)

print()
print("Stage 1 前 10 名參數組：")
display_columns = [
    "parameter_set_id",
    "rank_2d",
    "score_2d",
    "max_segment_p95_plastic_zone_thickness_estimate_m",
    "max_segment_p95_plastic_zone_ratio_to_radius",
    "max_stability_index",
    "pass_stage1",
    "danger_mileage",
    "danger_formation",
]
top10 = candidate_summary.sort_values("rank_2d").head(10)
print(top10[display_columns].to_string(index=False))
