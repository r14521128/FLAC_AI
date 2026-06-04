"""Entry point for the FLAC3D tunnel back-analysis calibration system.

Usage
-----
  # Full run with real FLAC3D:
  python main.py

  # Dry run (no FLAC3D, synthetic data, for pipeline testing):
  python main.py --dry-run

  # Resume from existing database (skip already-completed runs):
  python main.py --resume
"""

import os
import sys
import argparse

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so sub-packages import correctly
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents.orchestrator import Orchestrator

# ===========================================================================
# USER CONFIGURATION — edit these paths and values before running
# ===========================================================================
CONFIG = {
    # Path to FLAC3D 6.0 executable (also overridable via FLAC3D_EXE env var)
    "flac3d_exe": r"C:\Program Files\Itasca\FLAC3D600\exe64\flac3d600_gui.exe",

    # Monitoring data CSV (see data/monitoring/monitoring_data.csv for format)
    "monitoring_csv": os.path.join(PROJECT_ROOT, "data", "monitoring", "monitoring_data.csv"),

    # Optimisation budget
    "n_lhs_samples":  10,    # Phase 1: initial LHS explorations (2D space)
    "max_iterations": 60,    # Total budget (LHS + BO)

    # GLUE: runs with loss < glue_threshold * best_loss are "behavioural"
    "glue_threshold": 1.5,

    # Convergence: stop if best loss improves by < convergence_tol
    # for convergence_patience consecutive iterations
    "convergence_patience": 10,
    "convergence_tol":      0.001,

    # LHS random seed (for reproducibility)
    "lhs_seed": 42,

    # Dry-run mode: use synthetic FLAC3D output (no actual FLAC3D needed)
    "dry_run": False,
}
# ===========================================================================


def parse_args():
    p = argparse.ArgumentParser(description="Tunnel calibration AI agent")
    p.add_argument("--dry-run", action="store_true",
                   help="Use synthetic FLAC3D output for pipeline testing")
    p.add_argument("--resume", action="store_true",
                   help="Skip runs already in database (not yet implemented)")
    p.add_argument("--max-iter", type=int, default=None,
                   help="Override max_iterations")
    p.add_argument("--n-lhs", type=int, default=None,
                   help="Override n_lhs_samples")
    return p.parse_args()


def _check_prerequisites(config):
    errors = []

    if not config["dry_run"]:
        exe = config["flac3d_exe"]
        if not os.path.isfile(exe):
            errors.append(
                "FLAC3D executable not found: {}\n"
                "  → Edit CONFIG['flac3d_exe'] in main.py or set "
                "  the FLAC3D_EXE environment variable.".format(exe)
            )

    mon = config["monitoring_csv"]
    if not os.path.isfile(mon):
        errors.append(
            "Monitoring CSV not found: {}\n"
            "  → Place your monitoring data at that path.\n"
            "  → Format: station,step_pair,H1_mm,D1_mm,D2_mm\n"
            "  → Run with --dry-run to test without real data.".format(mon)
        )

    if errors:
        print("\n[main] PREREQUISITE ERRORS:")
        for e in errors:
            print("  ✗", e)
        return False
    return True


def main():
    args = parse_args()
    config = dict(CONFIG)

    if args.dry_run:
        config["dry_run"] = True
        print("[main] DRY RUN mode — using synthetic FLAC3D output.")

    if args.max_iter:
        config["max_iterations"] = args.max_iter

    if args.n_lhs:
        config["n_lhs_samples"] = args.n_lhs

    # Override FLAC3D exe from environment variable if set
    env_exe = os.environ.get("FLAC3D_EXE")
    if env_exe:
        config["flac3d_exe"] = env_exe
        print("[main] FLAC3D_EXE from env: {}".format(env_exe))

    # In dry-run mode, create a synthetic monitoring CSV if none exists
    if config["dry_run"]:
        _ensure_dummy_monitoring(config["monitoring_csv"])

    if not _check_prerequisites(config):
        sys.exit(1)

    print("\n[main] Starting calibration pipeline")
    print("[main] Config: LHS={}, MaxIter={}, DryRun={}".format(
        config["n_lhs_samples"], config["max_iterations"], config["dry_run"]
    ))

    orch = Orchestrator(config)
    results = orch.run()

    if results:
        print("\n[main] === CALIBRATION COMPLETE ===")
        print("[main] Best loss : {:.6f}".format(results["best_loss"]))
        print("[main] GLUE runs : {:d} / {:d}".format(
            results["n_glue"], results["n_total"]))
        print("[main] Parameters (mean +/- std):")
        from core.sampling import PARAM_NAMES
        for name in PARAM_NAMES:
            s = results[name]
            print("  {:12s}: {:.5f} +/- {:.5f}  [{:.5f}, {:.5f}]".format(
                name, s["mean"], s["std"], s["p5"], s["p95"]))


def _ensure_dummy_monitoring(csv_path):
    """Create synthetic monitoring data for dry-run testing."""
    import numpy as np
    import pandas as pd

    if os.path.exists(csv_path):
        return

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    stations = [2590, 2608, 2616, 2878, 2896, 2926, 2948]
    n_steps = 25
    rng = np.random.default_rng(0)
    rows = []
    for sta in stations:
        scale_h = rng.uniform(5, 15)   # mm
        scale_d = rng.uniform(2, 8)
        for step in range(1, n_steps + 1):
            t = step / n_steps
            rows.append({
                "station":  sta,
                "step_pair": step,
                "H1_mm":   -scale_h * t + rng.normal(0, 0.3),
                "D1_mm":   -scale_d * t + rng.normal(0, 0.1),
                "D2_mm":    scale_d * t + rng.normal(0, 0.1),
            })
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)
    print("[main] Synthetic monitoring CSV created: {}".format(csv_path))


if __name__ == "__main__":
    main()
