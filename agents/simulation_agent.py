"""Simulation Agent: write params.json -> launch FLAC3D -> collect CSV output."""

import json
import os
import subprocess
import time
import glob
import shutil
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FLAC3D_EXE = os.environ.get(
    "FLAC3D_EXE",
    r"C:\Program Files\Itasca\FLAC3D600\exe64\flac3d600_gui.exe",
)

PROJECT_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAC3D_DIR    = os.path.join(PROJECT_ROOT, "flac3d")
PARAMS_FILE   = os.path.join(FLAC3D_DIR, "params.json")
RESULTS_DIR   = os.path.join(PROJECT_ROOT, "data", "results")
MATERIAL_DAT  = os.path.join(FLAC3D_DIR, "material_setup.f3dat")
EXCAVATION_DAT = os.path.join(FLAC3D_DIR, "excavation.f3dat")

TIMEOUT_SEC = 7200
DONE_SENTINEL = os.path.join(FLAC3D_DIR, "simulation_done.flag")


def _write_params(params_dict):
    with open(PARAMS_FILE, "w") as f:
        json.dump(params_dict, f, indent=2)
    print("[SimAgent] Written params.json: {}".format(params_dict))


def _clear_sentinel():
    if os.path.exists(DONE_SENTINEL):
        os.remove(DONE_SENTINEL)


def _wait_for_completion(timeout=TIMEOUT_SEC):
    elapsed = 0
    interval = 5
    while elapsed < timeout:
        if os.path.exists(DONE_SENTINEL):
            return True
        time.sleep(interval)
        elapsed += interval
        if elapsed % 60 == 0:
            print("[SimAgent] Waiting... {}/{} sec".format(elapsed, timeout))
    return False


def _find_latest_csv():
    pattern = os.path.join(RESULTS_DIR, "run_*.csv")
    files = sorted(glob.glob(pattern), key=os.path.getmtime)
    return files[-1] if files else None


def _archive_csv(run_id):
    latest = _find_latest_csv()
    if latest is None:
        return None
    basename = os.path.basename(latest)
    if basename.startswith("run_") and basename != "run_latest.csv":
        dest = latest
    else:
        dest = os.path.join(RESULTS_DIR, "run_{:04d}.csv".format(run_id))
        shutil.move(latest, dest)
    return dest


def run(params_dict, run_id, dry_run=False):
    """Execute one FLAC3D simulation for the given parameters.

    Parameters
    ----------
    params_dict : dict
        Keys: k_E (Young's modulus scale), k_E_fault (fault zone scale).
    run_id : int
        Database run ID (used for CSV naming).
    dry_run : bool
        If True, skip actual FLAC3D launch (for testing pipeline).

    Returns
    -------
    csv_path : str or None
        Path to the output CSV, or None on failure.
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    _clear_sentinel()
    _write_params(params_dict)

    if dry_run:
        print("[SimAgent] DRY RUN — skipping FLAC3D launch.")
        _generate_dummy_csv(run_id, params_dict)
        return _archive_csv(run_id)

    if not os.path.isfile(FLAC3D_EXE):
        raise FileNotFoundError(
            "FLAC3D executable not found: {}\n"
            "Set FLAC3D_EXE environment variable or edit agents/simulation_agent.py".format(FLAC3D_EXE)
        )

    print("[SimAgent] Launching FLAC3D for run {:04d}...".format(run_id))
    proc = subprocess.Popen(
        [FLAC3D_EXE, "call", MATERIAL_DAT],
        cwd=PROJECT_ROOT,
    )

    completed = _wait_for_completion()
    if not completed:
        proc.kill()
        print("[SimAgent] TIMEOUT — run {:04d} killed.".format(run_id))
        return None

    proc.wait()
    csv_path = _archive_csv(run_id)
    if csv_path is None:
        print("[SimAgent] ERROR — no CSV found after run {:04d}.".format(run_id))
        return None

    print("[SimAgent] Run {:04d} completed. CSV: {}".format(run_id, csv_path))
    return csv_path


# ---------------------------------------------------------------------------
# Dry-run helper: generate synthetic CSV with plausible displacement trends
# ---------------------------------------------------------------------------
def _generate_dummy_csv(run_id, params):
    import numpy as np

    stations = [2590, 2608, 2616, 2878, 2896, 2926, 2948]
    n_steps = 30
    rng = np.random.default_rng(run_id)

    # Displacement magnitude scales inversely with Young's modulus
    k_E = params.get("k_E", 1.0)
    scale = 0.005 / max(k_E, 0.1)

    rows = []
    for step in range(1, n_steps + 1):
        row = {"step_pair": step,
               "L_xmin": 0.0, "L_xmax": 0.0,
               "R_xmin": 0.0, "R_xmax": 0.0}
        for sta in stations:
            t = step / n_steps
            noise = rng.normal(0, 0.0002)
            row["crown_{}_z".format(sta)]  = -scale * t * (1 + 0.1 * rng.random()) + noise
            row["wall_L_{}_y".format(sta)] = -scale * 0.3 * t + noise
            row["wall_R_{}_y".format(sta)] =  scale * 0.3 * t + noise
        rows.append(row)

    df = pd.DataFrame(rows)
    out_path = os.path.join(RESULTS_DIR, "run_{:04d}.csv".format(run_id))
    df.to_csv(out_path, index=False)
    print("[SimAgent] Dummy CSV written: {}".format(out_path))
