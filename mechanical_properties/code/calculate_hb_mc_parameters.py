from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
IN_DIR = BASE_DIR / "in"
OUT_DIR = BASE_DIR / "out"

BASE_UNITS = ["SS_NK", "Interbedded_ST", "SH_ST", "SS_NC", "SS_NC_damage"]
FAULT_COMPONENTS = ["Fault_up", "Fault_core", "Fault_down"]
DESIGN_UNITS = BASE_UNITS + FAULT_COMPONENTS
FINAL_ORDER = ["SS_NK", "Interbedded_ST", "SH_ST", "SS_NC", "Fault"]
DISTURBANCE_FACTOR = 0.5
MIN_GSI_GAP = 2.0
PLOT_DIR = OUT_DIR / "plot"
SS_NC_MERGE_WEIGHTS = {
    "SS_NC": 0.75,
    "SS_NC_damage": 0.25,
}
FAULT_WEIGHT_FACTORS = {
    "Fault_up": 1.5,
    "Fault_core": 0.5,
    "Fault_down": 1.5,
}

RAW_TO_MODEL_UNIT = {
    "SS with minor SH_(NK)": "SS_NK",
    "SS/SH Interbedded_(ST)": "Interbedded_ST",
    "SH with thin SS_(ST)": "SH_ST",
    "Fault_up": "Fault_up",
    "Fault_core": "Fault_core",
    "Fault_down": "Fault_down",
    "SS with thin SH_(NC)": "SS_NC",
    "SH with  SS": "SS_NC",
    "SS with thin SH_(NC).1": "SS_NC",
}

MI_DESIGN = {
    "SS_NK": 17.0,
    "Interbedded_ST": 12.0,
    "SH_ST": 8.0,
    "SS_NC": 7.0,
    "SS_NC_damage": 6.0,
    "Fault_up": 5.0,
    "Fault_core": 4.0,
    "Fault_down": 6.0,
}

POISSON_DESIGN = {
    "SS_NK": 0.25,
    "Interbedded_ST": 0.30,
    "SH_ST": 0.38,
    "SS_NC": 0.22,
    "SS_NC_damage": 0.28,
    "Fault_up": 0.34,
    "Fault_core": 0.38,
    "Fault_down": 0.32,
}

GSI_DESIGN_BASE = {
    "SS_NK": 50.0,
    "Interbedded_ST": 48.0,
    "SH_ST": 46.0,
    "SS_NC": 24.0,
    "SS_NC_damage": 20.0,
    "Fault_up": 15.0,
    "Fault_core": 10.0,
    "Fault_down": 18.0,
}


@dataclass
class UnitDesign:
    model_unit: str
    density_kg_m3: float
    sigma_ci_mpa: float
    mi: float
    gsi_from_rqd: float
    gsi: float
    d: float
    ei_mpa: float
    poisson: float
    cover_h_m: float


def find_input_file(keyword: str) -> Path:
    matches = [
        p for p in IN_DIR.glob("*.xlsx")
        if keyword in p.name and not p.name.startswith("~$")
    ]
    if len(matches) != 1:
        raise FileNotFoundError(f"找不到唯一的輸入檔：keyword={keyword}, matches={matches}")
    return matches[0]


def read_layer_table() -> pd.DataFrame:
    path = find_input_file("分層")
    df = pd.read_excel(path)
    df = df[pd.to_numeric(df["Depth"], errors="coerce").notna()].copy()
    return df


def read_test_workbook() -> tuple[Path, pd.ExcelFile]:
    path = find_input_file("試驗資料")
    return path, pd.ExcelFile(path)


def build_layer_intervals(layer_df: pd.DataFrame) -> pd.DataFrame:
    fixed_cols = ["Hole_ID", "E", "N", "Z", "Depth", "Distance"]
    layer_cols = [c for c in layer_df.columns if c not in fixed_cols]
    records = []

    for _, row in layer_df.iterrows():
        previous_bottom = 0.0
        bottoms = []
        for col in layer_cols:
            bottom = pd.to_numeric(pd.Series([row[col]]), errors="coerce").iloc[0]
            if pd.notna(bottom):
                bottoms.append((float(bottom), col))
        bottoms.sort(key=lambda x: x[0])

        for bottom, raw_unit in bottoms:
            model_unit = RAW_TO_MODEL_UNIT.get(str(raw_unit), str(raw_unit))
            if (
                str(raw_unit) == "SS with thin SH_(NC)"
                and str(row["Hole_ID"]).strip() in {"BH-4", "DH-8"}
                and previous_bottom > 0.0
            ):
                model_unit = "SS_NC_damage"
            records.append({
                "Hole_ID": row["Hole_ID"],
                "Distance_m": row.get("Distance", np.nan),
                "Surface_Z_m": row["Z"],
                "Depth_top_m": previous_bottom,
                "Depth_bottom_m": bottom,
                "Raw_unit": raw_unit,
                "Model_unit": model_unit,
            })
            previous_bottom = bottom

    return pd.DataFrame(records)


def assign_model_unit(intervals: pd.DataFrame, hole_id: str, depth_mid_m: float) -> tuple[str | None, str | None]:
    if pd.isna(hole_id) or pd.isna(depth_mid_m):
        return None, None
    rows = intervals[intervals["Hole_ID"].astype(str).str.strip() == str(hole_id).strip()]
    for _, row in rows.iterrows():
        if float(row["Depth_top_m"]) - 1.0e-9 <= float(depth_mid_m) <= float(row["Depth_bottom_m"]) + 1.0e-9:
            return str(row["Model_unit"]), str(row["Raw_unit"])
    return None, None


def append_samples(
    records: list[dict],
    intervals: pd.DataFrame,
    workbook_path: Path,
    sheet_name: str,
    test_type: str,
    depth_col: str,
    value_cols: list[str],
) -> None:
    df = pd.read_excel(workbook_path, sheet_name=sheet_name, header=1)
    for _, row in df.iterrows():
        model_unit, raw_unit = assign_model_unit(intervals, row["孔號"], row[depth_col])
        for value_col in value_cols:
            value = pd.to_numeric(pd.Series([row[value_col]]), errors="coerce").iloc[0]
            records.append({
                "test_type": test_type,
                "sheet": sheet_name,
                "hole_id": row["孔號"],
                "depth_mid_m": row[depth_col],
                "formation": row.get("地層", np.nan),
                "lithology": row.get("岩性描述", row.get("岩性", np.nan)),
                "raw_unit": raw_unit,
                "model_unit": model_unit,
                "parameter": value_col,
                "value": value,
            })


def collect_test_samples(intervals: pd.DataFrame, workbook_path: Path, xl: pd.ExcelFile) -> pd.DataFrame:
    records: list[dict] = []
    append_samples(records, intervals, workbook_path, xl.sheet_names[1], "RQD", "深度中點(m)", ["平均RQD(%)"])
    append_samples(records, intervals, workbook_path, xl.sheet_names[2], "Physical", "深度中點(m)", ["單位重(g/cm³)"])
    append_samples(records, intervals, workbook_path, xl.sheet_names[3], "UCS", "深度中點(m)", ["單壓強度qu(MPa)"])
    append_samples(records, intervals, workbook_path, xl.sheet_names[4], "Direct shear", "深度中點(m)", ["Cr(MPa)", "φr(°)"])
    append_samples(records, intervals, workbook_path, xl.sheet_names[5], "Triaxial summary", "深度中點(m)", ["Cp(MPa)", "φp(°)", "Cr(MPa)", "φr(°)"])
    append_samples(records, intervals, workbook_path, xl.sheet_names[6], "Elastic", "深度中點(m)", ["E靜(MPa)", "ν靜(-)"])
    return pd.DataFrame(records)


def get_stat(samples: pd.DataFrame, unit: str, parameter: str, stat: str = "median") -> float:
    values = samples[
        (samples["model_unit"] == unit)
        & (samples["parameter"] == parameter)
        & pd.to_numeric(samples["value"], errors="coerce").notna()
    ]["value"].astype(float)
    if values.empty:
        return np.nan
    if stat == "min":
        return float(values.min())
    if stat == "mean":
        return float(values.mean())
    if stat == "max":
        return float(values.max())
    return float(values.median())


def positive_cover_by_unit(intervals: pd.DataFrame) -> dict[str, float]:
    alignment_path = IN_DIR / "Shimen_Tunnel_3D_Alignment_1m.csv"
    alignment = pd.read_csv(alignment_path)
    cover_records = []

    for _, row in intervals.iterrows():
        if pd.isna(row["Distance_m"]):
            continue
        idx = (alignment["Mileage"] - float(row["Distance_m"])).abs().idxmin()
        crown_z = float(alignment.loc[idx, "Z_crown"])
        cover = float(row["Surface_Z_m"]) - crown_z
        if cover > 0:
            cover_records.append({
                "Model_unit": row["Model_unit"],
                "Hole_ID": row["Hole_ID"],
                "Distance_m": row["Distance_m"],
                "Cover_H_m": cover,
            })

    cover_df = pd.DataFrame(cover_records)
    if cover_df.empty:
        return {unit: 50.0 for unit in DESIGN_UNITS}

    covers = {}
    for unit in DESIGN_UNITS:
        vals = cover_df.loc[cover_df["Model_unit"] == unit, "Cover_H_m"]
        covers[unit] = float(vals.median()) if not vals.empty else np.nan

    global_median = float(cover_df["Cover_H_m"].median())
    for unit in DESIGN_UNITS:
        if pd.isna(covers[unit]):
            covers[unit] = global_median
    return covers


def gsi_from_rqd(samples: pd.DataFrame) -> dict[str, float]:
    gsi_raw = {}
    for unit in DESIGN_UNITS:
        rqd_median = get_stat(samples, unit, "平均RQD(%)")
        if pd.notna(rqd_median):
            gsi_raw[unit] = float(np.clip(rqd_median - 10.0, 10.0, 65.0))
        else:
            gsi_raw[unit] = np.nan
    return gsi_raw


def constrained_gsi(samples: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    gsi_raw = gsi_from_rqd(samples)
    gsi = dict(GSI_DESIGN_BASE)

    # RQD 是第一個估算來源；但最後材料表需同時滿足使用者指定的地質排序。
    # SS_NC 為隧道通過且較年輕、較弱地層，採比 RQD 初估更保守的上限。
    for unit in DESIGN_UNITS:
        if pd.isna(gsi_raw[unit]):
            continue
        if unit in {"SS_NC", "SS_NC_damage", "Fault_up", "Fault_core", "Fault_down"}:
            gsi[unit] = min(gsi_raw[unit], GSI_DESIGN_BASE[unit])
        elif unit in {"SS_NK", "Interbedded_ST", "SH_ST"}:
            gsi[unit] = max(gsi_raw[unit], GSI_DESIGN_BASE[unit])

    # 依使用者指定的地質強度排序，使強地層的 GSI 不低於弱地層。
    ordered_units = BASE_UNITS + ["Fault_down", "Fault_up", "Fault_core"]
    for i in range(len(ordered_units) - 2, -1, -1):
        stronger = ordered_units[i]
        weaker = ordered_units[i + 1]
        gsi[stronger] = max(gsi[stronger], gsi[weaker] + MIN_GSI_GAP)

    for unit in DESIGN_UNITS:
        gsi[unit] = float(np.clip(gsi[unit], 10.0, 65.0))
    return gsi_raw, gsi


def constrained_sigma_ci(samples: pd.DataFrame) -> dict[str, float]:
    sigma = {}
    ss_nc_median = get_stat(samples, "SS_NC", "單壓強度qu(MPa)")
    sigma["SS_NC"] = max(10.0, ss_nc_median if pd.notna(ss_nc_median) else 15.0)
    ss_nc_damage_raw = get_stat(samples, "SS_NC_damage", "單壓強度qu(MPa)")
    sigma["SS_NC_damage"] = min(
        sigma["SS_NC"] * 0.85,
        max(sigma["SS_NC"] * 0.55, ss_nc_damage_raw if pd.notna(ss_nc_damage_raw) else sigma["SS_NC"] * 0.60),
    )
    sigma["Fault_up"] = 1.00
    sigma["Fault_core"] = 0.50
    fault_down_raw = get_stat(samples, "Fault_down", "單壓強度qu(MPa)")
    sigma["Fault_down"] = min(
        sigma["SS_NC"] * 0.85,
        max(sigma["Fault_up"] * 1.5, fault_down_raw if pd.notna(fault_down_raw) else sigma["SS_NC"] * 0.70),
    )
    sigma["SH_ST"] = max(get_stat(samples, "SH_ST", "單壓強度qu(MPa)"), sigma["SS_NC"] * 1.15)
    sigma["Interbedded_ST"] = max(get_stat(samples, "Interbedded_ST", "單壓強度qu(MPa)"), sigma["SH_ST"] * 1.25)
    sigma["SS_NK"] = sigma["Interbedded_ST"] * 1.35
    return {unit: float(sigma[unit]) for unit in DESIGN_UNITS}


def constrained_ei(samples: pd.DataFrame) -> dict[str, float]:
    ei = {}
    ss_nc_e = get_stat(samples, "SS_NC", "E靜(MPa)")
    ei["SS_NC"] = max(1500.0, ss_nc_e if pd.notna(ss_nc_e) else 2200.0)
    ss_nc_damage_e = get_stat(samples, "SS_NC_damage", "E靜(MPa)")
    ei["SS_NC_damage"] = min(
        ei["SS_NC"] * 0.85,
        max(ei["SS_NC"] * 0.55, ss_nc_damage_e if pd.notna(ss_nc_damage_e) else ei["SS_NC"] * 0.60),
    )
    ei["Fault_up"] = 800.0
    ei["Fault_core"] = 500.0
    ei["Fault_down"] = min(ei["SS_NC"] * 0.75, 1500.0)
    ei["SH_ST"] = max(get_stat(samples, "SH_ST", "E靜(MPa)"), ei["SS_NC"] * 1.10)
    ei["Interbedded_ST"] = ei["SH_ST"] * 1.15
    ei["SS_NK"] = ei["Interbedded_ST"] * 1.25
    return {unit: float(ei[unit]) for unit in DESIGN_UNITS}


def density_design(samples: pd.DataFrame) -> dict[str, float]:
    density = {}
    for unit in DESIGN_UNITS:
        unit_weight = get_stat(samples, unit, "單位重(g/cm³)")
        if pd.notna(unit_weight):
            density[unit] = unit_weight * 1000.0
        else:
            density[unit] = np.nan

    density["SS_NK"] = density.get("SS_NK", np.nan)
    if pd.isna(density["SS_NK"]):
        density["SS_NK"] = max(v for v in density.values() if pd.notna(v)) + 20.0
    if pd.isna(density["Interbedded_ST"]):
        density["Interbedded_ST"] = np.nanmedian([density["SH_ST"], density["SS_NC"]])
    if pd.isna(density["SS_NC_damage"]):
        density["SS_NC_damage"] = np.nanmedian([density["SS_NC"], density["Fault_down"] if "Fault_down" in density else np.nan])
    if pd.isna(density["Fault_up"]):
        density["Fault_up"] = np.nanmedian([density["SS_NC"], density["SH_ST"]])
    if pd.isna(density["Fault_core"]):
        density["Fault_core"] = density["Fault_up"] - 30.0
    if pd.isna(density["Fault_down"]):
        density["Fault_down"] = np.nanmedian([density["Fault_up"], density["SS_NC"]])
    return {unit: float(density[unit]) for unit in DESIGN_UNITS}


def build_design_table(samples: pd.DataFrame, intervals: pd.DataFrame) -> list[UnitDesign]:
    density = density_design(samples)
    sigma_ci = constrained_sigma_ci(samples)
    gsi_raw, gsi = constrained_gsi(samples)
    ei = constrained_ei(samples)
    covers = positive_cover_by_unit(intervals)

    return [
        UnitDesign(
            model_unit=unit,
            density_kg_m3=density[unit],
            sigma_ci_mpa=sigma_ci[unit],
            mi=MI_DESIGN[unit],
            gsi_from_rqd=gsi_raw[unit],
            gsi=gsi[unit],
            d=DISTURBANCE_FACTOR,
            ei_mpa=ei[unit],
            poisson=POISSON_DESIGN[unit],
            cover_h_m=covers[unit],
        )
        for unit in DESIGN_UNITS
    ]


def fault_thickness_weights(intervals: pd.DataFrame) -> pd.DataFrame:
    fault_intervals = intervals[intervals["Model_unit"].isin(FAULT_COMPONENTS)].copy()
    fault_intervals["Thickness_m"] = fault_intervals["Depth_bottom_m"] - fault_intervals["Depth_top_m"]
    weights = (
        fault_intervals.groupby("Model_unit")["Thickness_m"]
        .sum()
        .reindex(FAULT_COMPONENTS)
        .fillna(0.0)
        .reset_index()
    )
    total = float(weights["Thickness_m"].sum())
    weights["Weight_from_thickness"] = weights["Thickness_m"] / total if total > 0 else 0.0
    weights["Weight_factor"] = weights["Model_unit"].map(FAULT_WEIGHT_FACTORS).astype(float)
    weights["Weighted_thickness_m"] = weights["Thickness_m"] * weights["Weight_factor"]
    adjusted_total = float(weights["Weighted_thickness_m"].sum())
    weights["Weight"] = weights["Weighted_thickness_m"] / adjusted_total if adjusted_total > 0 else 0.0
    return weights


def integrated_fault_material(component_material_df: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, wrow in weights.iterrows():
        unit = wrow["Model_unit"]
        mat = component_material_df.loc[component_material_df["model_unit"] == unit]
        if mat.empty:
            continue
        row = mat.iloc[0].to_dict()
        row["Weight"] = float(wrow["Weight"])
        rows.append(row)

    weighted = pd.DataFrame(rows)
    if weighted.empty:
        raise ValueError("Fault 子帶沒有可加權的材料參數。")

    out = {"model_unit": "Fault"}
    for col in ["density_kg_m3", "young_GPa", "poisson", "cohesion_kPa", "friction_deg", "tension_kPa"]:
        out[col] = float((weighted[col].astype(float) * weighted["Weight"]).sum())
    return pd.DataFrame([out])


def ss_nc_merge_weights() -> pd.DataFrame:
    weights = pd.DataFrame([
        {"Model_unit": unit, "Weight": weight}
        for unit, weight in SS_NC_MERGE_WEIGHTS.items()
    ])
    total = float(weights["Weight"].sum())
    weights["Weight"] = weights["Weight"] / total if total > 0 else 0.0
    return weights


def integrated_ss_nc_material(component_material_df: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, wrow in weights.iterrows():
        unit = wrow["Model_unit"]
        mat = component_material_df.loc[component_material_df["model_unit"] == unit]
        if mat.empty:
            continue
        row = mat.iloc[0].to_dict()
        row["Weight"] = float(wrow["Weight"])
        rows.append(row)

    weighted = pd.DataFrame(rows)
    if weighted.empty:
        raise ValueError("SS_NC / SS_NC_damage 沒有可加權的材料參數。")

    out = {"model_unit": "SS_NC"}
    for col in ["density_kg_m3", "young_GPa", "poisson", "cohesion_kPa", "friction_deg", "tension_kPa"]:
        out[col] = float((weighted[col].astype(float) * weighted["Weight"]).sum())
    return pd.DataFrame([out])


def hb_constants(sigma_ci_mpa: float, mi: float, gsi: float, d: float) -> tuple[float, float, float]:
    mb = mi * math.exp((gsi - 100.0) / (28.0 - 14.0 * d))
    s = math.exp((gsi - 100.0) / (9.0 - 3.0 * d))
    a = 0.5 + (1.0 / 6.0) * (math.exp(-gsi / 15.0) - math.exp(-20.0 / 3.0))
    return mb, s, a


def hb_sigma1(sigma3_mpa: np.ndarray, sigma_ci_mpa: float, mb: float, s: float, a: float) -> np.ndarray:
    return sigma3_mpa + sigma_ci_mpa * np.power(mb * sigma3_mpa / sigma_ci_mpa + s, a)


def rock_mass_strength_mpa(sigma_ci_mpa: float, mb: float, s: float, a: float) -> float:
    # Hoek et al. rock mass UCS used for tunnel sigma3max estimation.
    return (
        sigma_ci_mpa
        * (mb + 4.0 * s - a * (mb - 8.0 * s))
        * (mb / 4.0 + s) ** (a - 1.0)
        / (2.0 * (1.0 + a) * (2.0 + a))
    )


def tunnel_sigma3max_mpa(sigma_cm_mpa: float, density_kg_m3: float, cover_h_m: float) -> tuple[float, float]:
    gamma_h_mpa = density_kg_m3 * 9.81 * cover_h_m / 1.0e6
    sigma_cm_safe = max(sigma_cm_mpa, 1.0e-6)
    gamma_h_safe = max(gamma_h_mpa, 0.01)
    sigma3max = sigma_cm_safe * 0.47 * (sigma_cm_safe / gamma_h_safe) ** (-0.94)
    sigma3max = max(sigma3max, 0.01)
    return float(sigma3max), float(gamma_h_mpa)


def hoek_diederichs_erm_mpa(ei_mpa: float, gsi: float, d: float) -> float:
    reduction = 0.02 + (1.0 - d / 2.0) / (1.0 + math.exp((60.0 + 15.0 * d - gsi) / 11.0))
    return ei_mpa * reduction


def hb_tension_kpa(sigma_ci_mpa: float, mb: float, s: float, cohesion_mpa: float, friction_deg: float) -> float:
    hb_tension_mpa = s * sigma_ci_mpa / max(mb, 1.0e-12)
    phi_rad = math.radians(max(friction_deg, 1.0e-6))
    mc_tension_limit_mpa = cohesion_mpa / max(math.tan(phi_rad), 1.0e-12)
    return float(min(hb_tension_mpa, mc_tension_limit_mpa) * 1000.0)


def regress_mc_from_hb(
    sigma_ci_mpa: float,
    mb: float,
    s: float,
    a: float,
    sigma3max_mpa: float,
) -> dict[str, float | np.ndarray]:
    sigma3 = np.linspace(0.0, sigma3max_mpa, 160)
    sigma1 = hb_sigma1(sigma3, sigma_ci_mpa, mb, s, a)
    slope, intercept = np.polyfit(sigma3, sigma1, 1)
    fitted = slope * sigma3 + intercept
    ss_res = float(np.sum((sigma1 - fitted) ** 2))
    ss_tot = float(np.sum((sigma1 - np.mean(sigma1)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0

    sin_phi = (slope - 1.0) / (slope + 1.0)
    sin_phi = float(np.clip(sin_phi, 0.0, 0.999))
    phi_rad = math.asin(sin_phi)
    cohesion_mpa = intercept * (1.0 - sin_phi) / (2.0 * math.cos(phi_rad))

    return {
        "sigma3": sigma3,
        "sigma1": sigma1,
        "mc_sigma1": fitted,
        "regression_slope": float(slope),
        "regression_intercept_mpa": float(intercept),
        "regression_r2": float(r2),
        "cohesion_mpa": float(cohesion_mpa),
        "friction_deg": float(math.degrees(phi_rad)),
    }


def make_plots(curves: dict[str, dict[str, float | np.ndarray]], out_dir: Path) -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    plot_units = [unit for unit in DESIGN_UNITS if unit in curves]
    ncols = 2
    nrows = math.ceil(len(plot_units) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(13, 4.7 * nrows))
    axes = axes.ravel()
    for ax_idx, unit in enumerate(plot_units):
        ax = axes[ax_idx]
        data = curves[unit]
        ax.plot(data["sigma3"], data["sigma1"], label="Hoek-Brown 曲線", linewidth=2)
        ax.plot(data["sigma3"], data["mc_sigma1"], "--", label="MC 線性回歸", linewidth=2)
        ax.set_title(unit)
        ax.set_xlabel("σ3 (MPa)")
        ax.set_ylabel("σ1 (MPa)")
        ax.grid(True, alpha=0.3)
        ax.legend()
    for ax in axes[len(plot_units):]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_dir / "hb_mc_regression_all_units.png", dpi=220)
    plt.close(fig)

    for unit in plot_units:
        data = curves[unit]
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.plot(data["sigma3"], data["sigma1"], label="Hoek-Brown 曲線", linewidth=2.2)
        ax.plot(data["sigma3"], data["mc_sigma1"], "--", label="MC 線性回歸", linewidth=2.2)
        ax.set_title(f"{unit}：HB 轉等效 MC")
        ax.set_xlabel("σ3 (MPa)")
        ax.set_ylabel("σ1 (MPa)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / f"hb_mc_regression_{unit}.png", dpi=220)
        plt.close(fig)


def save_publication_bundle(fig: plt.Figure, out_base: Path, final_export: bool = False) -> None:
    fig.savefig(out_base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    if not final_export:
        return
    fig.savefig(out_base.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(out_base.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(out_base.with_suffix(".tiff"), dpi=600, bbox_inches="tight")


def make_composite_failure_plots(
    curves: dict[str, dict[str, float | np.ndarray]],
    hb_df: pd.DataFrame,
    material_df: pd.DataFrame,
    out_dir: Path,
    final_export: bool = False,
) -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["pdf.fonttype"] = 42

    composite_dir = out_dir
    composite_dir.mkdir(exist_ok=True)

    plot_units = [unit for unit in DESIGN_UNITS if unit in curves]
    for unit in plot_units:
        curve = curves[unit]
        hb = hb_df.loc[hb_df["model_unit"] == unit].iloc[0]
        mat = material_df.loc[material_df["model_unit"] == unit].iloc[0]

        sigma3 = np.asarray(curve["sigma3"], dtype=float)
        sigma1 = np.asarray(curve["sigma1"], dtype=float)
        mc_sigma1 = np.asarray(curve["mc_sigma1"], dtype=float)
        point_idx = np.linspace(0, len(sigma3) - 1, 8).astype(int)

        p = (sigma1 + sigma3) / 2.0
        q = (sigma1 - sigma3) / 2.0
        p_slope, p_intercept = np.polyfit(p, q, 1)
        q_fit = p_slope * p + p_intercept

        sigma_ci = float(hb["sigma_ci_MPa"])
        mb = float(hb["mb"])
        s = float(hb["s"])
        a = float(hb["a"])
        x_hb = sigma3 / sigma_ci
        y_hb = np.power((sigma1 - sigma3) / sigma_ci, 1.0 / a)
        y_hb_line = mb * x_hb + s

        c_mpa = float(mat["cohesion_kPa"]) / 1000.0
        phi_rad = math.radians(float(mat["friction_deg"]))
        max_sigma1 = max(float(sigma1.max()), float(mc_sigma1.max()))
        normal_axis = np.linspace(0.0, max_sigma1 * 1.08, 240)
        shear_envelope = c_mpa + normal_axis * math.tan(phi_rad)

        fig, axes = plt.subplots(2, 2, figsize=(10.5, 8.0))
        ax = axes[0, 0]
        ax.plot(sigma3, sigma1, color="#1f77b4", lw=2.0, label="Hoek-Brown")
        ax.plot(sigma3, mc_sigma1, color="#d62728", lw=1.8, ls="--", label="MC equivalent")
        ax.scatter(sigma3[point_idx], sigma1[point_idx], s=24, color="black", zorder=5, label="regression points")
        ax.set_title("A  Principal-stress fit")
        ax.set_xlabel(r"Minor principal stress, $\sigma_3$ (MPa)")
        ax.set_ylabel(r"Major principal stress, $\sigma_1$ (MPa)")
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False, fontsize=8)

        ax = axes[0, 1]
        ax.scatter(p[point_idx], q[point_idx], s=24, color="black", zorder=5, label="transformed points")
        ax.plot(p, q_fit, color="#d62728", lw=1.8, ls="--", label=f"q = {p_slope:.3f}p + {p_intercept:.3f}")
        ax.set_title("B  Mohr-Coulomb p-q regression")
        ax.set_xlabel(r"Mean stress, $p=(\sigma_1+\sigma_3)/2$ (MPa)")
        ax.set_ylabel(r"Shear stress, $q=(\sigma_1-\sigma_3)/2$ (MPa)")
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False, fontsize=8)

        ax = axes[1, 0]
        ax.scatter(x_hb[point_idx], y_hb[point_idx], s=24, color="black", zorder=5, label="HB points")
        ax.plot(x_hb, y_hb_line, color="#1f77b4", lw=1.8, label=f"y = {mb:.3f}x + {s:.2e}")
        ax.set_title("C  Hoek-Brown transformed line")
        ax.set_xlabel(r"$\sigma_3 / \sigma_{ci}$")
        ax.set_ylabel(r"$[(\sigma_1-\sigma_3)/\sigma_{ci}]^{1/a}$")
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False, fontsize=8)

        ax = axes[1, 1]
        theta = np.linspace(0, math.pi, 180)
        circle_idx = np.linspace(0, len(sigma3) - 1, 5).astype(int)
        for j, idx in enumerate(circle_idx):
            center = (sigma1[idx] + sigma3[idx]) / 2.0
            radius = (sigma1[idx] - sigma3[idx]) / 2.0
            x_circle = center + radius * np.cos(theta)
            y_circle = radius * np.sin(theta)
            ax.plot(x_circle, y_circle, color="#7f7f7f", lw=0.9, alpha=0.8)
            ax.scatter([center], [0], s=10, color="#7f7f7f", alpha=0.8)
        ax.plot(normal_axis, shear_envelope, color="#d62728", lw=1.8, label=rf"$\tau=c+\sigma\tan\phi$")
        ax.set_title("D  Mohr circles and MC envelope")
        ax.set_xlabel(r"Normal stress, $\sigma$ (MPa)")
        ax.set_ylabel(r"Shear stress, $\tau$ (MPa)")
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False, fontsize=8)

        fig.suptitle(
            f"{unit}: HB source curve and equivalent MC parameters "
            f"(c={float(mat['cohesion_kPa']):.1f} kPa, phi={float(mat['friction_deg']):.1f} deg)",
            fontsize=12,
            y=0.99,
        )
        fig.tight_layout(rect=(0, 0, 1, 0.965))
        save_publication_bundle(fig, composite_dir / f"failure_criteria_composite_{unit}", final_export=final_export)
        plt.close(fig)


def write_report(
    out_dir: Path,
    material_df: pd.DataFrame,
    component_material_df: pd.DataFrame,
    hb_df: pd.DataFrame,
    raw_stats: pd.DataFrame,
    ss_nc_weights: pd.DataFrame,
    fault_weights: pd.DataFrame,
) -> None:
    report_path = out_dir / "material_parameter_method_report.md"
    lines = []
    lines.append("# 岩體材料參數換算報告")
    lines.append("")
    lines.append("## 1. 目標參數")
    lines.append("")
    lines.append("本次輸出供 FLAC3D Mohr-Coulomb 材料使用的五個參數：")
    lines.append("")
    lines.append("- `density`：kg/m3")
    lines.append("- `young`：GPa")
    lines.append("- `poisson`：無因次")
    lines.append("- `cohesion`：kPa")
    lines.append("- `friction`：degree")
    lines.append("- `tension`：kPa")
    lines.append("")
    lines.append("## 2. 地質排序約束")
    lines.append("")
    lines.append("依使用者指定，強度排序固定為：")
    lines.append("")
    lines.append("```text")
    lines.append("SS_NK > Interbedded_ST > SH_ST > SS_NC > Fault")
    lines.append("```")
    lines.append("")
    lines.append("本版將 Fault 拆成 `Fault_up / Fault_core / Fault_down` 分別計算，最後依分層厚度加權整合成單一 `Fault`。")
    lines.append("試驗統計值若違反此排序，材料表採用排序約束後的設計值；原始統計仍另存於 `raw_group_statistics.csv` 供追查。")
    lines.append("")
    lines.append("## 3. UCS 取得方式")
    lines.append("")
    lines.append("UCS 是單軸抗壓強度。試體在無側向圍壓狀態下受軸向壓縮，破壞時最大荷重除以截面積：")
    lines.append("")
    lines.append("```text")
    lines.append("UCS = P_failure / A")
    lines.append("```")
    lines.append("")
    lines.append("本案 Excel 已提供 `單壓強度qu(MPa)`，因此不重做單位換算；只做孔號與深度對回模型地層。")
    lines.append("")
    lines.append("## 4. GSI 初估")
    lines.append("")
    lines.append("先用 RQD 的保守經驗式估算：")
    lines.append("")
    lines.append("```text")
    lines.append("GSI_raw = clip(RQD_median - 10, 10, 65)")
    lines.append("```")
    lines.append("")
    lines.append("若該地層沒有 RQD，使用保守地質初值；之後依強度排序做最小間距 2 的單調約束。")
    lines.append("表中的 `GSI_from_RQD` 是 RQD 初估值，`GSI` 是最後採用值。")
    lines.append("`SS_NC` 因屬南莊層且較年輕、較弱，雖然 RQD 初估較高，設計值仍採更保守上限。")
    lines.append("本版計算時將 `SS_NC` 拆成遠離斷層的 `SS_NC` 與受逆斷層損傷的 `SS_NC_damage`，最後再合併回單一 `SS_NC`。")
    lines.append("Fault 子帶中，`Fault_core` 採最低 GSI；`Fault_up/down` 視為 damage zone，允許比 core 稍高。")
    lines.append("Fault 整合時不再只用原始厚度比例，而是提高 up/down damage zone 權重、降低 core 權重，以測試較強的等效 Fault 參數。")
    lines.append("")
    lines.append("## 5. Hoek-Brown 參數")
    lines.append("")
    lines.append("採用廣義 Hoek-Brown：")
    lines.append("")
    lines.append("```text")
    lines.append("σ1 = σ3 + σci * (mb * σ3 / σci + s)^a")
    lines.append("mb = mi * exp((GSI - 100) / (28 - 14D))")
    lines.append("s  = exp((GSI - 100) / (9 - 3D))")
    lines.append("a  = 0.5 + (1/6) * (exp(-GSI/15) - exp(-20/3))")
    lines.append("```")
    lines.append("")
    lines.append("本次 `D = 0.5`，代表鑽炸與機械開挖造成的中等擾動。")
    lines.append("")
    lines.append("## 6. HB 轉等效 Mohr-Coulomb")
    lines.append("")
    lines.append("先估隧道問題的有效最大圍壓範圍：")
    lines.append("")
    lines.append("```text")
    lines.append("σ3max / σcm = 0.47 * (σcm / (γH))^(-0.94)")
    lines.append("γH = density * g * H")
    lines.append("```")
    lines.append("")
    lines.append("其中 H 由鑽孔地表高程與隧道 crown 線形高程估算。接著在 `0 <= σ3 <= σ3max` 上建立 HB 曲線，並用最小平方法擬合：")
    lines.append("")
    lines.append("```text")
    lines.append("σ1 = A * σ3 + B")
    lines.append("sin(phi) = (A - 1) / (A + 1)")
    lines.append("c = B * (1 - sin(phi)) / (2 * cos(phi))")
    lines.append("```")
    lines.append("")
    lines.append("## 7. 岩體變形模數")
    lines.append("")
    lines.append("採 Hoek-Diederichs 型式，由完整岩石靜彈性模數 Ei 折減為岩體模數 Erm：")
    lines.append("")
    lines.append("```text")
    lines.append("Erm = Ei * [0.02 + (1 - D/2) / (1 + exp((60 + 15D - GSI)/11))]")
    lines.append("young = Erm / 1000")
    lines.append("```")
    lines.append("")
    lines.append("## 8. 張力強度")
    lines.append("")
    lines.append("以 HB 岩體拉力強度與 MC 包絡線張力上限兩者取較小值：")
    lines.append("")
    lines.append("```text")
    lines.append("tension_HB = s * sigma_ci / mb")
    lines.append("tension_MC_limit = c / tan(phi)")
    lines.append("tension = min(tension_HB, tension_MC_limit)")
    lines.append("```")
    lines.append("")
    lines.append("## 9. 最終材料參數")
    lines.append("")
    lines.append(material_df.to_markdown(index=False, floatfmt=".4f"))
    lines.append("")
    lines.append("## 10. SS_NC 合併權重")
    lines.append("")
    lines.append("`SS_NC_damage` 保留在 component 表追蹤，但最終材料表中併回 `SS_NC`。合併時讓遠離斷層的 `SS_NC` 佔主要權重。")
    lines.append("")
    ss_nc_component_df = component_material_df[component_material_df["model_unit"].isin(["SS_NC", "SS_NC_damage"])]
    lines.append(ss_nc_component_df.to_markdown(index=False, floatfmt=".4f"))
    lines.append("")
    lines.append("合併權重：")
    lines.append("")
    lines.append(ss_nc_weights.to_markdown(index=False, floatfmt=".6g"))
    lines.append("")
    lines.append("## 11. Fault 子帶與厚度加權")
    lines.append("")
    lines.append("Fault 子帶材料參數：")
    lines.append("")
    fault_component_df = component_material_df[component_material_df["model_unit"].isin(FAULT_COMPONENTS)]
    lines.append(fault_component_df.to_markdown(index=False, floatfmt=".4f"))
    lines.append("")
    lines.append("厚度權重：")
    lines.append("")
    lines.append(fault_weights.to_markdown(index=False, floatfmt=".6g"))
    lines.append("")
    lines.append("## 12. HB 與回歸參數")
    lines.append("")
    lines.append(hb_df.to_markdown(index=False, floatfmt=".6g"))
    lines.append("")
    lines.append("## 13. 圖版說明")
    lines.append("")
    lines.append("新增 `plot/` 內的 composite 圖版，每個地層包含四個 panel：")
    lines.append("")
    lines.append("- A：`sigma3-sigma1` 空間中的 HB 曲線、等效 MC 線與回歸採樣點。")
    lines.append("- B：參考作業模板的 `p-q` 線性回歸點位圖。")
    lines.append("- C：廣義 HB 的轉換線性圖，顯示 `mb` 與 `s` 的來源。")
    lines.append("- D：`sigma-tau` 空間中的莫爾圓與 MC 抗剪包絡線。")
    lines.append("")
    lines.append("目前的點位是 HB 曲線在採用圍壓範圍內的回歸採樣點；原始三軸試驗並未提供完整 `sigma1-sigma3` 點列，因此未把試驗點偽裝成原始量測點。")
    lines.append("")
    lines.append("## 14. 原始統計摘要")
    lines.append("")
    lines.append(raw_stats.to_markdown(index=False, floatfmt=".6g"))
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main(final_figures: bool = False) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    layer_df = read_layer_table()
    workbook_path, xl = read_test_workbook()
    intervals = build_layer_intervals(layer_df)
    samples = collect_test_samples(intervals, workbook_path, xl)
    designs = build_design_table(samples, intervals)

    raw_stats = (
        samples.dropna(subset=["model_unit", "value"])
        .groupby(["model_unit", "parameter"])["value"]
        .agg(["count", "min", "median", "mean", "max"])
        .reset_index()
    )

    material_rows = []
    hb_rows = []
    curves = {}

    for design in designs:
        mb, s, a = hb_constants(design.sigma_ci_mpa, design.mi, design.gsi, design.d)
        sigma_cm = rock_mass_strength_mpa(design.sigma_ci_mpa, mb, s, a)
        sigma3max, gamma_h = tunnel_sigma3max_mpa(sigma_cm, design.density_kg_m3, design.cover_h_m)
        erm_mpa = hoek_diederichs_erm_mpa(design.ei_mpa, design.gsi, design.d)
        regression = regress_mc_from_hb(design.sigma_ci_mpa, mb, s, a, sigma3max)
        tension_kpa = hb_tension_kpa(
            design.sigma_ci_mpa,
            mb,
            s,
            float(regression["cohesion_mpa"]),
            float(regression["friction_deg"]),
        )
        curves[design.model_unit] = regression

        material_rows.append({
            "model_unit": design.model_unit,
            "density_kg_m3": design.density_kg_m3,
            "young_GPa": erm_mpa / 1000.0,
            "poisson": design.poisson,
            "cohesion_kPa": regression["cohesion_mpa"] * 1000.0,
            "friction_deg": regression["friction_deg"],
            "tension_kPa": tension_kpa,
        })
        hb_rows.append({
            "model_unit": design.model_unit,
            "sigma_ci_MPa": design.sigma_ci_mpa,
            "mi": design.mi,
            "GSI_from_RQD": design.gsi_from_rqd,
            "GSI": design.gsi,
            "D": design.d,
            "Ei_intact_MPa": design.ei_mpa,
            "mb": mb,
            "s": s,
            "a": a,
            "sigma_cm_MPa": sigma_cm,
            "cover_H_m": design.cover_h_m,
            "gammaH_MPa": gamma_h,
            "sigma3max_MPa": sigma3max,
            "regression_slope_A": regression["regression_slope"],
            "regression_intercept_B_MPa": regression["regression_intercept_mpa"],
            "regression_R2": regression["regression_r2"],
        })

    component_material_df = pd.DataFrame(material_rows)
    hb_df = pd.DataFrame(hb_rows)
    ss_nc_weights = ss_nc_merge_weights()
    ss_nc_integrated_df = integrated_ss_nc_material(component_material_df, ss_nc_weights)
    fault_weights = fault_thickness_weights(intervals)
    fault_integrated_df = integrated_fault_material(component_material_df, fault_weights)
    material_df = pd.concat([
        component_material_df[component_material_df["model_unit"].isin(["SS_NK", "Interbedded_ST", "SH_ST"])],
        ss_nc_integrated_df,
        fault_integrated_df,
    ], ignore_index=True)
    material_df["model_unit"] = pd.Categorical(material_df["model_unit"], categories=FINAL_ORDER, ordered=True)
    material_df = material_df.sort_values("model_unit").reset_index(drop=True)
    material_df["model_unit"] = material_df["model_unit"].astype(str)

    intervals.to_csv(OUT_DIR / "layer_intervals_assigned.csv", index=False, encoding="utf-8-sig")
    samples.to_csv(OUT_DIR / "test_samples_assigned.csv", index=False, encoding="utf-8-sig")
    raw_stats.to_csv(OUT_DIR / "raw_group_statistics.csv", index=False, encoding="utf-8-sig")
    material_df.to_csv(OUT_DIR / "material_parameters_mc.csv", index=False, encoding="utf-8-sig")
    component_material_df.to_csv(OUT_DIR / "material_parameters_mc_with_fault_components.csv", index=False, encoding="utf-8-sig")
    ss_nc_weights.to_csv(OUT_DIR / "ss_nc_component_merge_weights.csv", index=False, encoding="utf-8-sig")
    fault_weights.to_csv(OUT_DIR / "fault_component_thickness_weights.csv", index=False, encoding="utf-8-sig")
    hb_df.to_csv(OUT_DIR / "hb_regression_parameters.csv", index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(OUT_DIR / "mechanical_parameters_summary.xlsx", engine="openpyxl") as writer:
        material_df.to_excel(writer, sheet_name="MC_material_parameters", index=False)
        component_material_df.to_excel(writer, sheet_name="MC_fault_components", index=False)
        ss_nc_weights.to_excel(writer, sheet_name="SS_NC_merge_weights", index=False)
        fault_weights.to_excel(writer, sheet_name="Fault_thickness_weights", index=False)
        hb_df.to_excel(writer, sheet_name="HB_regression_parameters", index=False)
        raw_stats.to_excel(writer, sheet_name="Raw_group_statistics", index=False)
        samples.to_excel(writer, sheet_name="Assigned_samples", index=False)
        intervals.to_excel(writer, sheet_name="Layer_intervals", index=False)

    make_plots(curves, PLOT_DIR)
    make_composite_failure_plots(curves, hb_df, component_material_df, PLOT_DIR, final_export=final_figures)
    write_report(OUT_DIR, material_df, component_material_df, hb_df, raw_stats, ss_nc_weights, fault_weights)

    print("輸出完成：")
    print(OUT_DIR)
    print(material_df.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate HB-derived Mohr-Coulomb material parameters.")
    parser.add_argument(
        "--final-figures",
        action="store_true",
        help="Export publication figures as PNG, SVG, PDF, and TIFF. Default draft mode exports PNG only.",
    )
    args = parser.parse_args()
    main(final_figures=args.final_figures)
