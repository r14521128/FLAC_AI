"""Orchestrator: Phase 0 -> Phase 6 Bayesian Optimisation loop."""

import os
import sys
import json
import time
import pandas as pd
import numpy as np

from core import database as db
from core.sampling import latin_hypercube_sample, PARAM_NAMES
from core.loss_function import compute_loss, load_monitoring, load_simulation
from agents import simulation_agent as sim
from agents.calibration_agent import CalibrationAgent
from agents.lm_reporter import LmReporter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Orchestrator:
    """Drives the full calibration pipeline."""

    def __init__(self, config):
        self.cfg = config
        self.calib_agent = CalibrationAgent()
        self.lm_reporter = LmReporter(self.calib_agent)
        self._stall_counter = 0
        self._last_best_loss = None
        self.obs_df = None
        self._best_loss_history = []

    # ------------------------------------------------------------------
    # Phase 0: Initialise
    # ------------------------------------------------------------------
    def phase0_init(self):
        print("\n" + "="*60)
        print("PHASE 0 — Initialisation")
        print("="*60)
        db.initialize()
        self.obs_df = load_monitoring(self.cfg["monitoring_csv"])
        print("[Orch] Monitoring data loaded: {:d} rows from {:d} stations.".format(
            len(self.obs_df),
            self.obs_df["station"].nunique()
        ))

    # ------------------------------------------------------------------
    # Phase 1: Latin Hypercube Sampling
    # ------------------------------------------------------------------
    def phase1_lhs(self):
        print("\n" + "="*60)
        print("PHASE 1 — Latin Hypercube Sampling ({} points)".format(
            self.cfg["n_lhs_samples"]))
        print("="*60)
        samples = latin_hypercube_sample(
            self.cfg["n_lhs_samples"], seed=self.cfg.get("lhs_seed", 42)
        )
        print("[Orch] Generated {:d} LHS samples.".format(len(samples)))
        return samples

    # ------------------------------------------------------------------
    # Phase 2+3: Single simulation + loss evaluation
    # ------------------------------------------------------------------
    def _run_and_evaluate(self, params, run_id):
        t0 = time.time()

        csv_path = sim.run(params, run_id, dry_run=self.cfg.get("dry_run", False))
        if csv_path is None:
            db.update_run(run_id, loss=None, rmse=None, pearson_r=None,
                          csv_path=None, status="failed")
            return None

        sim_df = load_simulation(csv_path)
        total_loss, rmse, r_mean, detail = compute_loss(sim_df, self.obs_df)

        db.update_run(run_id, loss=total_loss, rmse=rmse,
                      pearson_r=r_mean, csv_path=csv_path, status="completed")

        elapsed = time.time() - t0
        print("[Orch] run {:04d} | loss={:.6f}  rmse={:.3f}mm  r={:.4f}  "
              "({:.1f}s)".format(run_id, total_loss, rmse, r_mean, elapsed))
        return total_loss

    # ------------------------------------------------------------------
    # Phase 4+5: Calibration agent updates GP and suggests next point
    # ------------------------------------------------------------------
    def _update_and_suggest(self):
        runs = db.get_all_runs()
        self.calib_agent.fit(runs)
        return self.calib_agent.suggest()

    # ------------------------------------------------------------------
    # Convergence check
    # ------------------------------------------------------------------
    def _has_converged(self):
        patience = self.cfg.get("convergence_patience", 10)
        tol = self.cfg.get("convergence_tol", 0.001)
        hist = self._best_loss_history

        if len(hist) < patience + 1:
            return False

        recent = hist[-patience:]
        best_recent = min(recent)
        best_before = hist[-(patience + 1)]

        improvement = (best_before - best_recent) / (abs(best_before) + 1e-12)
        if improvement < tol:
            print("[Orch] Converged: improvement={:.6f} < tol={:.6f}".format(
                improvement, tol))
            return True
        return False

    # ------------------------------------------------------------------
    # Phase 6: GLUE analysis and report
    # ------------------------------------------------------------------
    def phase6_glue(self):
        print("\n" + "="*60)
        print("PHASE 6 — GLUE Analysis")
        print("="*60)

        runs = db.get_all_runs()
        if not runs:
            print("[Orch] No completed runs — nothing to report.")
            return

        best_run = db.get_best_run()
        best_loss = best_run["loss"]
        glue_runs = db.get_best_runs(self.cfg.get("glue_threshold", 1.5))

        print("[Orch] Best loss: {:.6f}".format(best_loss))
        print("[Orch] Best params: k_E={k_E:.4f}  k_E_fault={k_E_fault:.4f}".format(
            **best_run))
        print("[Orch] GLUE behavioural runs: {:d} / {:d}".format(
            len(glue_runs), len(runs)))

        out_dir = os.path.join(PROJECT_ROOT, "output", "calibration_report")
        os.makedirs(out_dir, exist_ok=True)

        # GLUE CSV
        glue_df = pd.DataFrame(glue_runs)
        glue_csv = os.path.join(out_dir, "glue_analysis.csv")
        glue_df.to_csv(glue_csv, index=False)
        print("[Orch] GLUE results saved: {}".format(glue_csv))

        # Best params JSON with uncertainty
        stats = {}
        for name in PARAM_NAMES:
            vals = [r[name] for r in glue_runs]
            stats[name] = {
                "best":   float(best_run[name]),
                "mean":   float(np.mean(vals)),
                "std":    float(np.std(vals)),
                "p5":     float(np.percentile(vals, 5)),
                "p95":    float(np.percentile(vals, 95)),
            }
        stats["best_loss"] = best_loss
        stats["n_glue"] = len(glue_runs)
        stats["n_total"] = len(runs)

        best_json = os.path.join(out_dir, "best_params.json")
        with open(best_json, "w") as f:
            json.dump(stats, f, indent=2)
        print("[Orch] Best params + uncertainty: {}".format(best_json))

        self._plot_convergence(runs, out_dir)

        return stats

    def _plot_convergence(self, runs, out_dir):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            losses = [r["loss"] for r in runs]
            best_so_far = [min(losses[:i+1]) for i in range(len(losses))]

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

            ax1.plot(losses, "o-", alpha=0.5, label="Current run loss", markersize=3)
            ax1.plot(best_so_far, "r-", linewidth=2, label="Best loss so far")
            ax1.axvline(self.cfg["n_lhs_samples"] - 1, color="gray",
                        linestyle="--", label="LHS / BO boundary")
            ax1.set_ylabel("Loss")
            ax1.legend()
            ax1.set_title("Calibration Convergence")
            ax1.grid(True, alpha=0.3)

            colors = ["#1f77b4", "#ff7f0e"]
            for k, name in enumerate(PARAM_NAMES):
                vals = [r[name] for r in runs]
                ax2.plot(vals, "o-", alpha=0.4, color=colors[k],
                         label=name, markersize=3)
            ax2.set_xlabel("Iteration")
            ax2.set_ylabel("Parameter value")
            ax2.legend(loc="upper right")
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            png_path = os.path.join(out_dir, "convergence_plot.png")
            plt.savefig(png_path, dpi=150)
            plt.close()
            print("[Orch] Convergence plot saved: {}".format(png_path))
        except Exception as e:
            print("[Orch] Warning: could not save convergence plot: {}".format(e))

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def run(self):
        self.phase0_init()
        lhs_queue = self.phase1_lhs()

        n_iter = 0
        max_iter = self.cfg["max_iterations"]

        print("\n" + "="*60)
        print("PHASE 2-5 — Simulation + Bayesian Optimisation loop")
        print("="*60)

        while n_iter < max_iter:
            if lhs_queue:
                params = lhs_queue.pop(0)
                source = "LHS"
            elif self.calib_agent.is_ready():
                params = _update_and_suggest_safe(self)
                source = "BO"
            else:
                from core.sampling import latin_hypercube_sample as lhs
                params = lhs(1, seed=n_iter + 9999)[0]
                source = "random"

            print("\n[Orch] Iter {:03d}/{:03d} [{source}]: "
                  "k_E={k_E:.4f}  k_E_fault={k_E_fault:.4f}".format(
                      n_iter + 1, max_iter, source=source, **params))

            run_id = db.insert_run(**params)
            loss = self._run_and_evaluate(params, run_id)
            n_iter += 1

            if loss is not None:
                current_best = min(
                    (r["loss"] for r in db.get_all_runs()), default=loss
                )
                self._best_loss_history.append(current_best)

                if self._last_best_loss is not None:
                    improvement = (self._last_best_loss - current_best) / (abs(self._last_best_loss) + 1e-12)
                    if improvement < 0.01:
                        self._stall_counter += 1
                    else:
                        self._stall_counter = 0
                self._last_best_loss = current_best

                if db.count_completed() >= 5:
                    runs = db.get_all_runs()
                    self.calib_agent.fit(runs)

                is_periodic = (n_iter % 5 == 0)
                is_stall = (self._stall_counter >= 3)

                if is_periodic or is_stall:
                    if is_periodic and is_stall:
                        trigger = "both"
                    elif is_periodic:
                        trigger = "periodic"
                    else:
                        trigger = "stall"

                    all_runs = db.get_all_runs()
                    global_best = db.get_best_run()
                    history = all_runs[-10:] if len(all_runs) >= 10 else all_runs
                    best_run = db.get_best_run()
                    best_loss_detail = {
                        "loss": best_run["loss"],
                        "rmse": best_run.get("rmse", None),
                        "pearson_r": best_run.get("pearson_r", None),
                    }
                    best_params_report = {
                        k: best_run[k] for k in PARAM_NAMES
                    }

                    current_run = next(
                        (r for r in all_runs if r["run_id"] == run_id), None
                    )
                    sim_df_report = (
                        load_simulation(current_run["csv_path"])
                        if current_run and current_run.get("csv_path")
                        else None
                    )

                    if sim_df_report is not None:
                        self.lm_reporter.generate_report(
                            iteration=n_iter,
                            trigger=trigger,
                            best_params=best_params_report,
                            best_loss_detail=best_loss_detail,
                            history=history,
                            global_best=global_best,
                            sim_df=sim_df_report,
                            obs_df=self.obs_df,
                        )

                if self._has_converged():
                    print("[Orch] Early stopping at iteration {:d}.".format(n_iter))
                    break

        return self.phase6_glue()


def _update_and_suggest_safe(orch):
    try:
        return orch._update_and_suggest()
    except Exception as e:
        print("[Orch] GP suggest failed ({}), using random fallback.".format(e))
        from core.sampling import latin_hypercube_sample as lhs
        import random
        return lhs(1, seed=random.randint(0, 9999))[0]
