"""LM Reporter: LM Studio local API for Markdown analysis reports."""

import os
import json
import numpy as np
import pandas as pd
import requests

from core.sampling import PARAM_NAMES, normalize, denormalize

# ---------------------------------------------------------------------------
# LM Studio settings
# ---------------------------------------------------------------------------
LM_API_URL = "http://localhost:1234/v1/chat/completions"
LM_MODEL_ID = "google/gemma-4-e2b"
LM_TIMEOUT = 120

REPORT_STATIONS = [2896, 2616]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(PROJECT_ROOT, "output", "calibration_report")

SYSTEM_PROMPT = (
    "你是一位專業的岩石力學工程師助理，專門協助分析隧道數值模擬參數反算結果。\n"
    "請用繁體中文回應，語氣專業但易懂，避免過度技術性術語。"
)


class LmReporter:

    def __init__(self, calib_agent):
        self._calib = calib_agent

    # ------------------------------------------------------------------
    def generate_report(
        self,
        iteration,
        trigger,
        best_params,
        best_loss_detail,
        history,
        global_best,
        sim_df,
        obs_df,
    ):
        try:
            user_prompt = self._build_user_prompt(
                iteration, trigger, best_params, best_loss_detail,
                history, global_best, sim_df, obs_df,
            )
            md_content = self._call_lm(user_prompt)
            if not md_content:
                print("[LmReporter] Warning: empty LM response, skipping.")
                return

            filepath = self._save_report(iteration, trigger, md_content)
            print("[LmReporter] Report saved: {}".format(filepath))

        except requests.ConnectionError:
            print("[LmReporter] Warning: cannot connect to LM Studio ({}), skipping.".format(LM_API_URL))
        except requests.Timeout:
            print("[LmReporter] Warning: LM Studio timeout ({}s), skipping.".format(LM_TIMEOUT))
        except Exception as e:
            print("[LmReporter] Warning: report generation failed ({}), skipping.".format(e))

    # ------------------------------------------------------------------
    def _call_lm(self, user_prompt):
        payload = {
            "model": LM_MODEL_ID,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 2048,
        }
        resp = requests.post(LM_API_URL, json=payload, timeout=LM_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip() if content else ""

    # ------------------------------------------------------------------
    def _build_user_prompt(
        self, iteration, trigger, best_params, best_loss_detail,
        history, global_best, sim_df, obs_df,
    ):
        trigger_reason = self._format_trigger_reason(iteration, trigger)
        comparison = self._extract_station_comparison(sim_df, obs_df)
        history_table = self._format_history_table(history)
        sensitivity = self._compute_sensitivity(best_params)

        prompt = (
            "【觸發原因】\n"
            "{trigger_reason}\n"
            "\n"
            "【本輪最佳參數】\n"
            "k_E (Young整體縮放): {k_E}\n"
            "k_E_fault (斷層帶額外縮放): {k_E_fault}\n"
            "\n"
            "【本輪 loss 明細】\n"
            "RMSE: {rmse} mm\n"
            "Pearson r: {pearson_r}\n"
            "總 loss: {total_loss}\n"
            "\n"
            "【監測點模擬 vs 現地對比】\n"
            "{comparison}"
            "\n"
            "【最近 10 輪 loss 趨勢】\n"
            "輪次 | loss | RMSE | Pearson r\n"
            "{history_table}\n"
            "\n"
            "【全局最佳組】\n"
            "輪次 {best_run_id}：loss={best_loss}，\n"
            "k_E={best_k_E}，k_E_fault={best_k_E_fault}\n"
            "\n"
            "【參數敏感度（GP偏微分）】\n"
            "k_E: {sens_k_E}\n"
            "k_E_fault: {sens_k_E_fault}\n"
            "（數值越大代表該參數對 loss 影響越大）\n"
            "\n"
            "請依序輸出以下五個區塊，每個區塊用 Markdown 二級標題（##）標示：\n"
            "## 1. 本輪摘要\n"
            "## 2. 結果解讀\n"
            "## 3. 參數敏感度觀察\n"
            "## 4. 歷史趨勢\n"
            "## 5. 建議\n"
        ).format(
            trigger_reason=trigger_reason,
            k_E=best_params.get("k_E", "N/A"),
            k_E_fault=best_params.get("k_E_fault", "N/A"),
            rmse=best_loss_detail.get("rmse", "N/A"),
            pearson_r=best_loss_detail.get("pearson_r", "N/A"),
            total_loss=best_loss_detail.get("loss", "N/A"),
            comparison=comparison,
            history_table=history_table,
            best_run_id=global_best.get("run_id", "N/A"),
            best_loss=global_best.get("loss", "N/A"),
            best_k_E=global_best.get("k_E", "N/A"),
            best_k_E_fault=global_best.get("k_E_fault", "N/A"),
            sens_k_E=sensitivity.get("k_E", "N/A"),
            sens_k_E_fault=sensitivity.get("k_E_fault", "N/A"),
        )
        return prompt

    # ------------------------------------------------------------------
    @staticmethod
    def _format_trigger_reason(iteration, trigger):
        if trigger == "both":
            return "第 {} 輪定期報告（同時偵測到 loss 停滯）".format(iteration)
        elif trigger == "stall":
            return "連續 3 輪 loss 改善幅度 < 1%，搜索可能停滯"
        else:
            return "第 {} 輪定期報告".format(iteration)

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_station_comparison(sim_df, obs_df):
        lines = []
        sim_last = sim_df.sort_values("step_pair").iloc[-1]

        for station in REPORT_STATIONS:
            crown_col = "crown_{}_z".format(station)
            wall_l_col = "wall_L_{}_y".format(station)
            wall_r_col = "wall_R_{}_y".format(station)

            sim_L = sim_last.get(crown_col, None)
            sim_wall_l = sim_last.get(wall_l_col, 0.0)
            sim_wall_r = sim_last.get(wall_r_col, 0.0)
            sim_H = -float(sim_wall_l) + float(sim_wall_r) if sim_wall_l is not None else None

            obs_sta = obs_df[obs_df["station"] == station]
            if not obs_sta.empty:
                obs_last = obs_sta.sort_values("step_pair").iloc[-1]
                obs_L = obs_last["H1_mm"] / 1000.0
                obs_D1 = obs_last["D1_mm"] / 1000.0
                obs_D2 = obs_last["D2_mm"] / 1000.0
                obs_H = -obs_D1 + obs_D2
            else:
                obs_L = None
                obs_H = None

            lines.append("x={}：".format(station))
            lines.append("  L（頂拱）模擬={} m，監測={} m".format(
                _fmt(sim_L), _fmt(obs_L)))
            lines.append("  H（側壁）模擬={} m，監測={} m".format(
                _fmt(sim_H), _fmt(obs_H)))

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    @staticmethod
    def _format_history_table(history):
        lines = []
        for r in history:
            lines.append("{} | {:.6f} | {:.3f} | {:.4f}".format(
                r.get("run_id", "?"),
                r.get("loss", 0.0),
                r.get("rmse", 0.0),
                r.get("pearson_r", 0.0),
            ))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def _compute_sensitivity(self, best_params):
        if not self._calib.is_ready():
            return {n: "N/A (GP not ready)" for n in PARAM_NAMES}

        x0 = normalize(best_params)
        delta = 0.01
        sensitivity = {}

        for i, name in enumerate(PARAM_NAMES):
            x_plus = x0.copy()
            x_minus = x0.copy()
            x_plus[i] = min(x0[i] + delta, 1.0)
            x_minus[i] = max(x0[i] - delta, 0.0)

            actual_delta = x_plus[i] - x_minus[i]
            if actual_delta < 1e-12:
                sensitivity[name] = 0.0
                continue

            mu_plus = self._calib.gp.predict(x_plus.reshape(1, -1))[0]
            mu_minus = self._calib.gp.predict(x_minus.reshape(1, -1))[0]

            sensitivity[name] = round(float(abs(mu_plus - mu_minus) / actual_delta), 6)

        return sensitivity

    # ------------------------------------------------------------------
    @staticmethod
    def _save_report(iteration, trigger, md_content):
        os.makedirs(REPORT_DIR, exist_ok=True)

        if trigger == "both":
            filename = "report_round_{:03d}_stall.md".format(iteration)
        elif trigger == "stall":
            filename = "report_stall_{:03d}.md".format(iteration)
        else:
            filename = "report_round_{:03d}.md".format(iteration)

        filepath = os.path.join(REPORT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        return filepath


def _fmt(val):
    if val is None:
        return "N/A"
    return "{:.6f}".format(float(val))
