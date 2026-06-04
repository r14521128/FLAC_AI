"""Loss function: weighted RMSE + (1 - Pearson r) across all monitoring channels."""

import numpy as np
import pandas as pd

# Monitoring stations (x-coordinates) and displacement channels
STATIONS = [2590, 2608, 2616, 2878, 2896, 2926, 2948]
CHANNELS = ["H1", "D1", "D2"]   # crown, left wall, right wall  (mm)

# Column mapping: simulation CSV uses these column name patterns
SIM_COL_MAP = {
    (station, ch): f"{col_prefix}_{station}_{suffix}"
    for station in STATIONS
    for ch, col_prefix, suffix in [
        ("H1", "crown",  "z"),
        ("D1", "wall_L", "y"),
        ("D2", "wall_R", "y"),
    ]
}

# Monitoring CSV column names (in mm)
OBS_H1 = "H1_mm"
OBS_D1 = "D1_mm"
OBS_D2 = "D2_mm"

WEIGHT_RMSE = 0.5
WEIGHT_CORR = 0.5


def _pearson_r(a, b):
    """Pearson correlation; returns 0 if either array has zero variance."""
    if len(a) < 2:
        return 0.0
    a_std = np.std(a)
    b_std = np.std(b)
    if a_std < 1e-12 or b_std < 1e-12:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _align(sim_series, obs_series):
    """Align sim and obs by step_pair index using inner join.

    Both inputs are pandas Series indexed by step_pair (int).
    Returns (sim_aligned, obs_aligned) as numpy arrays.
    """
    combined = pd.concat(
        [sim_series.rename("sim"), obs_series.rename("obs")], axis=1
    ).dropna()
    if len(combined) < 2:
        return None, None
    return combined["sim"].values, combined["obs"].values


def compute_loss(sim_df, obs_df):
    """Compute scalar loss between simulation and monitoring data.

    Parameters
    ----------
    sim_df : pd.DataFrame
        FLAC3D output CSV. Must have 'step_pair' column and displacement
        columns named as in SIM_COL_MAP. Units: metres.
    obs_df : pd.DataFrame
        Monitoring CSV. Must have 'station', 'step_pair', 'H1_mm',
        'D1_mm', 'D2_mm' columns. Units: millimetres.

    Returns
    -------
    total_loss : float
    rmse_mean  : float  (mm)
    r_mean     : float  (0~1)
    detail     : dict   per-channel breakdown
    """
    sim_df = sim_df.copy()
    sim_df.set_index("step_pair", inplace=True)

    channel_losses = []
    rmse_list = []
    r_list = []
    detail = {}

    for station in STATIONS:
        obs_sta = obs_df[obs_df["station"] == station].copy()
        if obs_sta.empty:
            continue
        obs_sta = obs_sta.set_index("step_pair")

        for ch, obs_col in [("H1", OBS_H1), ("D1", OBS_D1), ("D2", OBS_D2)]:
            # Simulation column (convert m → mm)
            sim_col = SIM_COL_MAP.get((station, ch))
            if sim_col is None or sim_col not in sim_df.columns:
                continue
            sim_series = sim_df[sim_col] * 1000.0   # m → mm

            if obs_col not in obs_sta.columns:
                continue
            obs_series = obs_sta[obs_col]

            sim_arr, obs_arr = _align(sim_series, obs_sta[obs_col])
            if sim_arr is None:
                continue

            rmse = float(np.sqrt(np.mean((sim_arr - obs_arr) ** 2)))
            r = _pearson_r(sim_arr, obs_arr)

            # Normalise RMSE by observed displacement range (avoid div/0)
            obs_range = float(np.ptp(obs_arr)) if np.ptp(obs_arr) > 1e-6 else 1.0
            rmse_norm = rmse / obs_range

            channel_loss = WEIGHT_RMSE * rmse_norm + WEIGHT_CORR * (1.0 - r)
            channel_losses.append(channel_loss)
            rmse_list.append(rmse)
            r_list.append(r)

            detail[f"{station}_{ch}"] = {
                "rmse_mm": rmse,
                "pearson_r": r,
                "channel_loss": channel_loss,
                "n_points": len(sim_arr),
            }

    if not channel_losses:
        return 9999.0, 9999.0, 0.0, {}

    total_loss = float(np.mean(channel_losses))
    rmse_mean  = float(np.mean(rmse_list))
    r_mean     = float(np.mean(r_list))
    return total_loss, rmse_mean, r_mean, detail


def load_monitoring(csv_path):
    """Load monitoring CSV into a DataFrame."""
    df = pd.read_csv(csv_path)
    required = {"station", "step_pair", OBS_H1, OBS_D1, OBS_D2}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Monitoring CSV missing columns: {missing}")
    df["station"] = df["station"].astype(int)
    df["step_pair"] = df["step_pair"].astype(int)
    return df


def load_simulation(csv_path):
    """Load FLAC3D simulation output CSV."""
    df = pd.read_csv(csv_path)
    if "step_pair" not in df.columns:
        raise ValueError("Simulation CSV missing 'step_pair' column")
    df["step_pair"] = df["step_pair"].astype(int)
    return df
