from __future__ import annotations

from datetime import datetime
from pathlib import Path
import math
import shutil

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name.lower() == "code" else SCRIPT_DIR
INT_DIR = PROJECT_ROOT / "int"
OUT_DIR = PROJECT_ROOT / "out" / "2d_plane_screening" / "parameter_sweep"
OUT_DIR.mkdir(parents=True, exist_ok=True)

STATS_CSV = INT_DIR / "00_material_parameter_statistics.csv"
ASSUMPTIONS_CSV = INT_DIR / "00_hb_parameter_assumptions.csv"
SUMMARY_CSV = OUT_DIR / "stage1_hb_material_parameter_update_summary.csv"

FORMATIONS = ["SS_NK", "Interbedded_ST", "SH_ST", "SS_NC", "Fault"]

# mi/GSI are not direct measurements in the provided Excel files.
# Keep them explicit and editable instead of hiding them in the screening code.
DEFAULT_HB_ASSUMPTIONS = {
    "SS_NK": {"mi_min": 12.0, "mi_q50": 17.0, "mi_max": 22.0, "GSI_min": 35.0, "GSI_q50": 45.0, "GSI_max": 55.0},
    "Interbedded_ST": {"mi_min": 7.0, "mi_q50": 9.0, "mi_max": 12.0, "GSI_min": 30.0, "GSI_q50": 38.0, "GSI_max": 45.0},
    "SH_ST": {"mi_min": 4.0, "mi_q50": 6.0, "mi_max": 8.0, "GSI_min": 25.0, "GSI_q50": 33.0, "GSI_max": 40.0},
    "SS_NC": {"mi_min": 12.0, "mi_q50": 17.0, "mi_max": 22.0, "GSI_min": 40.0, "GSI_q50": 48.0, "GSI_max": 55.0},
    "Fault": {"mi_min": 3.0, "mi_q50": 4.0, "mi_max": 6.0, "GSI_min": 15.0, "GSI_q50": 22.0, "GSI_max": 30.0},
}

FAULT_FALLBACKS = {
    "density_kg_m3": [2490.0],
    "E_GPa": [0.2, 0.3, 0.6],
    "nu": [0.30, 0.35],
    "c_MPa": [0.020, 0.027, 0.030],
    "phi_deg": [16.0, 17.0, 20.0],
    "sigma_ci_MPa": [5.0, 10.0, 15.0],
}


def describe(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise ValueError("no finite values")
    return {
        "min": float(np.min(arr)),
        "q25": float(np.quantile(arr, 0.25)),
        "q50": float(np.quantile(arr, 0.50)),
        "mean": float(np.mean(arr)),
        "max": float(np.max(arr)),
        "n": int(arr.size),
    }


def find_workbook(keyword: str) -> Path:
    matches = [p for p in INT_DIR.glob("*.xlsx") if keyword in p.name]
    if not matches:
        raise FileNotFoundError(f"Cannot find workbook containing {keyword} in {INT_DIR}")
    return max(matches, key=lambda p: p.stat().st_mtime)


def map_formation(stratum: object, lithology: object) -> str | None:
    text = f"{stratum} {lithology}"
    if "砂頁岩" in text:
        return "Interbedded_ST"
    if "頁岩" in text:
        return "SH_ST"
    if "砂岩" in text:
        return "SS_NC" if "南莊" in text else "SS_NK"
    return None


def add_value(values: dict[tuple[str, str], list[float]], formation: str | None, parameter: str, value: object) -> None:
    if formation is None:
        return
    x = pd.to_numeric(value, errors="coerce")
    if np.isfinite(x):
        values.setdefault((formation, parameter), []).append(float(x))


def build_assumptions() -> pd.DataFrame:
    if ASSUMPTIONS_CSV.exists():
        return pd.read_csv(ASSUMPTIONS_CSV, encoding="utf-8-sig")

    rows = []
    for formation, vals in DEFAULT_HB_ASSUMPTIONS.items():
        row = {"formation": formation, "D_hb": 0.5}
        row.update(vals)
        row["source"] = "initial_engineering_assumption_user_review_required"
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(ASSUMPTIONS_CSV, index=False, encoding="utf-8-sig")
    return table


def load_excel_values() -> tuple[dict[tuple[str, str], list[float]], list[dict]]:
    workbook = find_workbook("力學試驗資料彙整")
    values: dict[tuple[str, str], list[float]] = {}
    summary: list[dict] = []

    physical = pd.read_excel(workbook, sheet_name=2, header=1)
    for _, row in physical.iterrows():
        formation = map_formation(row.get("地層"), row.get("岩性描述"))
        add_value(values, formation, "density_kg_m3", row.get("單位重(g/cm³)") * 1000.0)

    ucs = pd.read_excel(workbook, sheet_name=3, header=1)
    for _, row in ucs.iterrows():
        formation = map_formation(row.get("地層"), row.get("岩性描述"))
        add_value(values, formation, "sigma_ci_MPa", row.get("單壓強度qu(MPa)"))

    direct = pd.read_excel(workbook, sheet_name=4, header=1)
    for _, row in direct.iterrows():
        formation = map_formation(row.get("地層"), row.get("岩性描述"))
        add_value(values, formation, "c_MPa", row.get("Cr(MPa)"))
        add_value(values, formation, "phi_deg", row.get("φr(°)"))

    triaxial = pd.read_excel(workbook, sheet_name=5, header=1)
    for _, row in triaxial.iterrows():
        formation = map_formation(row.get("地層"), row.get("岩性描述"))
        add_value(values, formation, "c_MPa", row.get("Cr(MPa)"))
        add_value(values, formation, "phi_deg", row.get("φr(°)"))

    elastic = pd.read_excel(workbook, sheet_name=6, header=1)
    for _, row in elastic.iterrows():
        formation = map_formation(row.get("地層"), row.get("岩性描述"))
        add_value(values, formation, "E_GPa", row.get("E靜(MPa)") / 1000.0)
        add_value(values, formation, "nu", row.get("ν靜(-)"))

    for formation in FORMATIONS:
        for parameter in ["density_kg_m3", "E_GPa", "nu", "c_MPa", "phi_deg", "sigma_ci_MPa"]:
            count = len(values.get((formation, parameter), []))
            summary.append(
                {
                    "formation": formation,
                    "parameter": parameter,
                    "n_excel_values": count,
                    "source": str(workbook),
                }
            )
    return values, summary


def row_from_values(formation: str, parameter: str, unit: str, values: list[float], source: str) -> dict:
    stats = describe(values)
    return {
        "formation": formation,
        "parameter": parameter,
        "unit": unit,
        "min": stats["min"],
        "q25": stats["q25"],
        "q50": stats["q50"],
        "mean": stats["mean"],
        "max": stats["max"],
        "source": source,
    }


def previous_values(previous_stats: pd.DataFrame, formation: str, parameter: str) -> list[float]:
    if previous_stats.empty:
        return []
    row = previous_stats[
        (previous_stats["formation"].astype(str) == formation)
        & (previous_stats["parameter"].astype(str) == parameter)
    ]
    if row.empty:
        return []
    r = row.iloc[0]
    return [float(r["min"]), float(r["q25"]), float(r["q50"]), float(r["mean"]), float(r["max"])]


def main() -> None:
    assumptions = build_assumptions().set_index("formation")
    excel_values, summary = load_excel_values()
    previous_stats = pd.read_csv(STATS_CSV, encoding="utf-8-sig") if STATS_CSV.exists() else pd.DataFrame()

    if STATS_CSV.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(STATS_CSV, INT_DIR / f"00_material_parameter_statistics.backup-{stamp}-pre-hb.csv")

    rows: list[dict] = []
    target_rows = [
        ("density_kg_m3", "kg/m3"),
        ("E_GPa", "GPa"),
        ("nu", "-"),
        ("c_MPa", "MPa"),
        ("phi_deg", "deg"),
        ("sigma_ci_MPa", "MPa"),
    ]

    for formation in FORMATIONS:
        for parameter, unit in target_rows:
            vals = excel_values.get((formation, parameter), [])
            source = "力學試驗資料彙整.xlsx"
            if not vals and formation == "Fault":
                vals = FAULT_FALLBACKS[parameter]
                source = "fault_core_engineering_fallback_user_review_required"
            if not vals:
                vals = previous_values(previous_stats, formation, parameter)
                source = "fallback_previous_stats_missing_excel_value"
            if not vals:
                raise ValueError(f"{formation} has no values for {parameter}; add data or fallback before running.")
            rows.append(row_from_values(formation, parameter, unit, vals, source))

        assumption = assumptions.loc[formation]
        rows.append(row_from_values(formation, "mi", "-", [assumption["mi_min"], assumption["mi_q50"], assumption["mi_max"]], str(assumption.get("source", ""))))
        rows.append(row_from_values(formation, "GSI", "-", [assumption["GSI_min"], assumption["GSI_q50"], assumption["GSI_max"]], str(assumption.get("source", ""))))
        rows.append(row_from_values(formation, "D_hb", "-", [float(assumption["D_hb"])], "user_fixed_D_0.5"))

    pd.DataFrame(rows).to_csv(STATS_CSV, index=False, encoding="utf-8-sig")
    pd.DataFrame(summary).to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")

    print(f"updated: {STATS_CSV}")
    print(f"assumptions: {ASSUMPTIONS_CSV}")
    print(f"summary: {SUMMARY_CSV}")


if __name__ == "__main__":
    main()
