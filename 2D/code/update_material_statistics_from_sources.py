from __future__ import annotations

from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name.lower() == "code" else SCRIPT_DIR
INT_DIR = PROJECT_ROOT / "int"
OUT_DIR = PROJECT_ROOT / "out" / "2d_plane_screening" / "parameter_sweep"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CURRENT_STATS_CSV = INT_DIR / "00_material_parameter_statistics.csv"
BACKUP_STATS_CSV = INT_DIR / "00_material_parameter_statistics_before_gpa_update.csv"
UPDATED_STATS_CSV = CURRENT_STATS_CSV
UPDATE_SUMMARY_CSV = OUT_DIR / "stage1_material_parameter_range_update_summary.csv"
COMPARE_CSV = OUT_DIR / "stage1_material_parameter_range_before_after_gpa.csv"
COMPARE_FIG = OUT_DIR / "figures" / "stage1_material_parameter_range_update_comparison.png"


FORMATION_MAP = {
    "Massive SS": "SS_NK",
    "Interbedded": "Interbedded_ST",
    "SH w/ thin SS": "SH_ST",
    "SS w/ thin SH": "SS_NC",
    "Main fault zone": "Fault",
    "Fault damage zone": "Fault_damage_zone_not_used_as_fault_core",
}

TARGET_ROWS = [
    ("density_kg_m3", "kg/m3"),
    ("E_GPa", "GPa"),
    ("nu", "-"),
    ("c_MPa", "MPa"),
    ("phi_deg", "deg"),
]


def find_param_sources_csv() -> Path:
    """從 iCloudDrive 內尋找本次上傳的 param_sources.csv。"""
    candidates = [
        p
        for p in (Path.home() / "iCloudDrive").rglob("param_sources.csv")
        if "ARMS" in str(p)
    ]
    if not candidates:
        raise FileNotFoundError("找不到 ARMS 目錄內的 param_sources.csv")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def map_formation(source_name: str) -> str:
    text = str(source_name)
    lower = text.lower()
    for key, formation in FORMATION_MAP.items():
        if key.lower() in lower:
            return formation
    raise ValueError(f"無法對應地層名稱：{source_name}")


def parse_pair(value: object) -> tuple[float, float]:
    """解析 'cohesion / friction' 格式；cohesion 單位為 Pa，friction 單位為 deg。"""
    parts = str(value).split("/")
    if len(parts) != 2:
        raise ValueError(f"無法解析強度參數組：{value}")
    return float(parts[0].strip()), float(parts[1].strip())


def describe_values(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        raise ValueError("沒有可用數值")
    return {
        "min": float(np.min(arr)),
        "q25": float(np.quantile(arr, 0.25)),
        "q50": float(np.quantile(arr, 0.50)),
        "mean": float(np.mean(arr)),
        "max": float(np.max(arr)),
        "n": int(len(arr)),
    }


def old_row_as_target_unit(old_stats: pd.DataFrame, formation: str, old_names: list[str], new_name: str, unit: str) -> dict:
    old = old_stats[(old_stats["formation"] == formation) & (old_stats["parameter"].isin(old_names))]
    if old.empty:
        raise ValueError(f"{formation} 缺少舊參數可回填：{old_names}")
    row = old.iloc[0].copy()
    old_unit = str(row["unit"]).lower()
    target_unit = str(unit).lower()
    factor = 1.0
    if old_unit == "mpa" and target_unit == "gpa":
        factor = 0.001
    elif old_unit == "gpa" and target_unit == "mpa":
        factor = 1000.0
    return {
        "formation": formation,
        "parameter": new_name,
        "unit": unit,
        "min": float(row["min"]) * factor,
        "q25": float(row["q25"]) * factor,
        "q50": float(row["q50"]) * factor,
        "mean": float(row["mean"]) * factor,
        "max": float(row["max"]) * factor,
        "source": "fallback_previous_stats_no_uploaded_value",
        "n": 0,
    }


def build_uploaded_statistics(source_csv: Path, old_stats: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(source_csv, encoding="utf-8-sig")
    formation_col, _hole_col, _depth_col, test_col, param_col, value_col = list(raw.columns)
    raw["formation"] = raw[formation_col].map(map_formation)

    values: dict[tuple[str, str], list[float]] = {}
    notes: list[dict] = []

    for _, row in raw.iterrows():
        formation = row["formation"]
        parameter = str(row[param_col]).strip()
        value = row[value_col]

        if formation == "Fault_damage_zone_not_used_as_fault_core":
            notes.append(
                {
                    "formation": formation,
                    "parameter": parameter,
                    "action": "skipped_fault_damage_zone_not_fault_core",
                    "value": value,
                }
            )
            continue

        if parameter == "density(kg/m3)":
            values.setdefault((formation, "density_kg_m3"), []).append(float(value))
        elif parameter == "E_static(Pa)":
            values.setdefault((formation, "E_GPa"), []).append(float(value) / 1.0e9)
        elif parameter == "nu":
            values.setdefault((formation, "nu"), []).append(float(value))
        elif parameter in {"Cp(Pa) / phi_p(deg)", "Cr(Pa) / phi_r(deg)"}:
            cohesion_pa, friction_deg = parse_pair(value)
            values.setdefault((formation, "c_MPa"), []).append(cohesion_pa / 1.0e6)
            values.setdefault((formation, "phi_deg"), []).append(friction_deg)
        else:
            notes.append(
                {
                    "formation": formation,
                    "parameter": parameter,
                    "action": "skipped_unknown_parameter",
                    "value": value,
                }
            )

    formations = ["SS_NK", "Interbedded_ST", "SH_ST", "SS_NC", "Fault"]
    records: list[dict] = []
    summary_rows: list[dict] = []

    for formation in formations:
        for parameter, unit in TARGET_ROWS:
            key = (formation, parameter)
            if key in values:
                stats = describe_values(values[key])
                source = f"{source_csv.name}; uploaded_mechanical_test_values"
                records.append(
                    {
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
                )
                summary_rows.append(
                    {
                        "formation": formation,
                        "parameter": parameter,
                        "unit": unit,
                        "source_action": "updated_from_uploaded",
                        "n_uploaded_values": stats["n"],
                        "min": stats["min"],
                        "max": stats["max"],
                    }
                )
            else:
                if parameter == "E_GPa":
                    fallback = old_row_as_target_unit(old_stats, formation, ["E_GPa", "E_MPa", "E"], parameter, unit)
                elif parameter == "c_MPa":
                    fallback = old_row_as_target_unit(old_stats, formation, ["c_MPa", "c_GPa", "cohesion", "c"], parameter, unit)
                else:
                    fallback = old_row_as_target_unit(old_stats, formation, [parameter], parameter, unit)
                records.append({k: fallback[k] for k in ["formation", "parameter", "unit", "min", "q25", "q50", "mean", "max", "source"]})
                summary_rows.append(
                    {
                        "formation": formation,
                        "parameter": parameter,
                        "unit": unit,
                        "source_action": fallback["source"],
                        "n_uploaded_values": 0,
                        "min": fallback["min"],
                        "max": fallback["max"],
                    }
                )

    return pd.DataFrame(records), pd.DataFrame(summary_rows + notes)


def normalize_for_compare(table: pd.DataFrame, label: str) -> pd.DataFrame:
    """把舊表與新表統一成 E=GPa、c=MPa，方便前後比較。"""
    rows = []
    for _, row in table.iterrows():
        parameter = row["parameter"]
        unit = row["unit"]
        factor = 1.0
        if parameter == "E_MPa":
            parameter = "E_GPa"
            unit = "GPa"
            factor = 0.001
        elif parameter == "c_GPa":
            parameter = "c_MPa"
            unit = "MPa"
            factor = 1000.0
        elif parameter == "c_MPa":
            parameter = "c_MPa"
            unit = "MPa"
            factor = 1.0
        rows.append(
            {
                "version": label,
                "formation": row["formation"],
                "parameter": parameter,
                "unit": unit,
                "min": float(row["min"]) * factor,
                "q50": float(row["q50"]) * factor,
                "max": float(row["max"]) * factor,
                "source": row.get("source", ""),
            }
        )
    return pd.DataFrame(rows)


def write_compare_outputs(old_stats: pd.DataFrame, updated_stats: pd.DataFrame) -> None:
    compare = pd.concat(
        [
            normalize_for_compare(old_stats, "before"),
            normalize_for_compare(updated_stats, "after"),
        ],
        ignore_index=True,
    )
    compare = compare[
        compare["parameter"].isin(["E_GPa", "c_MPa", "phi_deg", "density_kg_m3", "nu"])
    ].copy()
    compare.to_csv(COMPARE_CSV, index=False, encoding="utf-8-sig")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return

    COMPARE_FIG.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = [
        "Microsoft JhengHei",
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    formations = ["SS_NK", "Interbedded_ST", "SH_ST", "SS_NC", "Fault"]
    parameters = ["E_GPa", "c_MPa", "phi_deg", "density_kg_m3", "nu"]
    colors = {"before": "#9e9ac8", "after": "#2ca25f"}
    fig, axes = plt.subplots(len(parameters), 1, figsize=(11, 13), sharey=False)

    for ax, parameter in zip(axes, parameters):
        subset = compare[compare["parameter"] == parameter]
        y_base = np.arange(len(formations))
        for offset, version in [(-0.16, "before"), (0.16, "after")]:
            version_table = subset[subset["version"] == version].set_index("formation")
            for y_index, formation in enumerate(formations):
                if formation not in version_table.index:
                    continue
                row = version_table.loc[formation]
                ax.hlines(
                    y_index + offset,
                    row["min"],
                    row["max"],
                    color=colors[version],
                    linewidth=3,
                )
                ax.plot(row["q50"], y_index + offset, marker="o", color=colors[version], markersize=5)
        unit = subset["unit"].dropna().iloc[0] if not subset.empty else ""
        ax.set_yticks(y_base)
        ax.set_yticklabels(formations)
        ax.set_xlabel(f"{parameter} ({unit})")
        ax.set_title(f"{parameter}：最小值 - 中位數 - 最大值")
        ax.grid(axis="x", alpha=0.25)

    axes[0].legend(
        handles=[
            plt.Line2D([0], [0], color=colors["before"], lw=3, marker="o", label="更新前"),
            plt.Line2D([0], [0], color=colors["after"], lw=3, marker="o", label="更新後"),
        ],
        loc="best",
    )
    fig.suptitle("Stage 1 材料參數區間更新前後比較", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(COMPARE_FIG, dpi=200)
    plt.close(fig)


def main() -> None:
    source_csv = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else find_param_sources_csv()
    if not CURRENT_STATS_CSV.exists():
        raise FileNotFoundError(f"找不到目前統計表：{CURRENT_STATS_CSV}")

    if not BACKUP_STATS_CSV.exists():
        shutil.copy2(CURRENT_STATS_CSV, BACKUP_STATS_CSV)
    fallback_stats = pd.read_csv(BACKUP_STATS_CSV, encoding="utf-8-sig")
    current_stats = pd.read_csv(CURRENT_STATS_CSV, encoding="utf-8-sig")
    updated_stats, update_summary = build_uploaded_statistics(source_csv, fallback_stats)

    updated_stats.to_csv(UPDATED_STATS_CSV, index=False, encoding="utf-8-sig")
    update_summary.to_csv(UPDATE_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    write_compare_outputs(current_stats, updated_stats)

    print("已更新 Stage 1 材料參數統計表")
    print(f"source_csv: {source_csv}")
    print(f"updated_stats_csv: {UPDATED_STATS_CSV}")
    print(f"backup_csv: {BACKUP_STATS_CSV}")
    print(f"update_summary_csv: {UPDATE_SUMMARY_CSV}")
    print(f"compare_csv: {COMPARE_CSV}")
    print(f"compare_figure: {COMPARE_FIG}")
    print()
    print(updated_stats.to_string(index=False))


if __name__ == "__main__":
    main()
