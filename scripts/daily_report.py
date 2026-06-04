# -*- coding: utf-8 -*-
"""每日 FLAC3D 進度報告（無人值守，本機自動執行 + Email 寄送）。

掃描 SCAN_ROOTS 下「距上次報告以來」有變動的檔案，用規則式判讀「每個資料夾
做了什麼」（不列檔名/日期），並從監測 CSV 抽出實際數據（步數、頂拱沉降、收斂、
塑性區…）寫成敘述。時間窗內有更新的「圖片檔」直接當附件寄出（不自繪圖）。

★ 純 Python（stdlib），完全不呼叫任何 AI/雲端 API → 每天執行 0 成本、不耗額度。
輸出：output/daily_report/report_YYYY-MM-DD_HHMM.html（本機留存）。
由 Windows 工作排程器每天觸發。
"""

import os
import re
import csv
import json
import smtplib
import mimetypes
from email.message import EmailMessage
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "output", "daily_report")
STATE_FILE = os.path.join(OUT_DIR, ".last_report")
MAIL_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mail_config.json")

SCAN_ROOTS = ["2D", "3D_far", "3D_small", "AI_交接"]
EXCLUDE_DIRS = {"__pycache__", ".git", ".ipynb_checkpoints", ".vscode"}

SAVE_EXTS = {".f3sav", ".sav", ".f3prj"}
SCRIPT_EXTS = {".f3dat", ".py", ".ps1", ".f3fis", ".fis", ".bat"}
DOC_EXTS = {".md"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg"}

MAX_ATTACH = 30
MAX_TOTAL_MB = 20
CSV_PEEK_MAX = 3 * 1024 * 1024   # 只深讀 <3MB 的 CSV


# ---------------------------------------------------------------------------
# 變動偵測
# ---------------------------------------------------------------------------
def get_since():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return datetime.fromisoformat(f.read().strip())
        except Exception:
            pass
    return datetime.now() - timedelta(hours=24)


def save_state(ts):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(ts.isoformat())


def scan_changes(since):
    groups = {}
    since_ts = since.timestamp()
    for root_name in SCAN_ROOTS:
        root_dir = os.path.join(ROOT, root_name)
        if not os.path.isdir(root_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                if st.st_mtime <= since_ts:
                    continue
                rel_to_root = os.path.relpath(full, root_dir)
                parts = rel_to_root.split(os.sep)
                key = root_name if len(parts) == 1 else "{}/{}".format(root_name, parts[0])
                groups.setdefault(key, []).append((full, st.st_mtime, st.st_size, fn))
    return groups


def human_size(n):
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return "{:.0f} {}".format(n, unit)
        n /= 1024.0
    return "{:.1f} TB".format(n)


# ---------------------------------------------------------------------------
# 監測 CSV 數據抽取（兩種格式都吃）
# ---------------------------------------------------------------------------
def _last_valid_rows(full):
    with open(full, newline="", encoding="utf-8", errors="ignore") as f:
        rd = csv.reader(f)
        header = next(rd, None)
        rows = [r for r in rd if r and any(c.strip() for c in r)]
    return header, rows


def extract_monitor(full):
    """回傳監測摘要 dict 或 None。支援遠場(crownNNNN_z)與小模型(crown_uz)。"""
    try:
        if os.path.getsize(full) > CSV_PEEK_MAX:
            return None
        header, rows = _last_valid_rows(full)
        if not header or len(rows) < 1:
            return None
        low = [h.strip().lower() for h in header]
        idx = {h: i for i, h in enumerate(low)}
        last = rows[-1]

        def fval(name):
            i = idx.get(name)
            if i is None or i >= len(last):
                return None
            try:
                return float(last[i])
            except ValueError:
                return None

        stations = []   # (label, settle_mm, conv_mm or None)

        # 格式 A：遠場大模型 crownNNNN_z（位移, m）
        far_cols = [(h, i) for h, i in idx.items() if re.match(r"crown\d+_z$", h)]
        if far_cols:
            for h, i in sorted(far_cols):
                sta = re.search(r"\d+", h).group()
                try:
                    settle = float(last[i]) * 1000.0
                except (ValueError, IndexError):
                    continue
                conv = fval("conv" + sta)
                stations.append((sta, settle, conv * 1000.0 if conv is not None else None))

        # 格式 B：小模型 crown_uz（位移, m），斷面取 crown_x
        elif "crown_uz" in idx:
            settle = fval("crown_uz")
            if settle is not None:
                sta_x = fval("crown_x")
                sta = str(int(round(sta_x))) if sta_x is not None else "?"
                conv = None
                wl, wr = fval("walll_uy"), fval("wallr_uy")
                if wl is not None and wr is not None:
                    conv = (wr - wl) * 1000.0
                stations.append((sta, settle * 1000.0, conv))

        if not stations:
            return None

        # 步數
        step = None
        for k in ("step", "step_pair"):
            if k in idx:
                try:
                    step = int(float(last[idx[k]]))
                except (ValueError, IndexError):
                    pass
                break
        if step is None:
            step = len(rows)

        return {
            "stations": stations,
            "step": step,
            "converged": fval("converged"),
            "plastic_nzone": fval("plastic_nzone"),
            "n_lined": fval("n_lined"),
        }
    except Exception:
        return None


def _scenario(fname):
    n = fname.lower()
    if "unsup" in n:
        return "無支撐開挖"
    if "smoke" in n:
        return "襯砌試跑(smoke)"
    if "lined" in n or "liner" in n:
        return "襯砌支撐開挖"
    if "excav" in n or "monitor" in n:
        return "開挖監測"
    return "監測"


# ---------------------------------------------------------------------------
# 每個資料夾的敘述摘要
# ---------------------------------------------------------------------------
def summarize_group(items):
    bullets = []
    cat = {"save": [], "script": 0, "log": 0, "doc": 0, "image": 0, "data": 0}
    csv_files = []
    for full, mt, sz, fn in items:
        ext = os.path.splitext(fn)[1].lower()
        if ext in SAVE_EXTS:
            cat["save"].append((sz, mt))
        elif ext in SCRIPT_EXTS:
            cat["script"] += 1
        elif ext == ".log":
            cat["log"] += 1
        elif ext in DOC_EXTS:
            cat["doc"] += 1
        elif ext in IMAGE_EXTS:
            cat["image"] += 1
        elif ext == ".csv":
            csv_files.append((full, mt, sz, fn))
            cat["data"] += 1
        else:
            cat["data"] += 1

    # 監測數據（取最新的 1~2 個有效監測 CSV）
    monitored = 0
    for full, mt, sz, fn in sorted(csv_files, key=lambda x: x[1], reverse=True):
        if monitored >= 2:
            break
        m = extract_monitor(full)
        if not m:
            continue
        monitored += 1
        parts = []
        for sta, settle, conv in m["stations"]:
            seg = "斷面 {} 頂拱沉降 {:+.1f} mm".format(sta, settle)
            if conv is not None:
                seg += "、水平收斂 {:+.1f} mm".format(conv)
            parts.append(seg)
        detail = "<b>{}</b>：算到第 {} 步".format(_scenario(fn), m["step"])
        if m["converged"] is not None:
            detail += "（{}）".format("已收斂" if m["converged"] else "未收斂")
        detail += "，" + "；".join(parts)
        extra = []
        if m["plastic_nzone"]:
            extra.append("塑性區約 {:.0f} 個 zone".format(m["plastic_nzone"]))
        if m["n_lined"]:
            extra.append("已裝襯砌 {:.0f} 面".format(m["n_lined"]))
        if extra:
            detail += "（{}）".format("、".join(extra))
        bullets.append(detail)

    # 計算進度（存檔）
    if cat["save"]:
        biggest = human_size(max(s for s, _ in cat["save"]))
        bullets.append("完成 {} 個階段存檔（最大 {}），代表這些計算已算到段落、可續用。".format(
            len(cat["save"]), biggest))
    # log（計算有在跑）
    if cat["log"]:
        bullets.append("{} 個計算 log 更新，表示這段期間有實際在跑/重跑計算。".format(cat["log"]))
    # 中間資料（扣掉已當監測敘述的 CSV，避免重複計）
    other_data = max(0, cat["data"] - monitored)
    if other_data:
        bullets.append("輸出/更新 {} 個資料檔（CSV、應力/邊界等中間結果）。".format(other_data))
    # 腳本
    if cat["script"]:
        bullets.append("調整或新增 {} 支計算腳本（FISH/.f3dat/Python）。".format(cat["script"]))
    # 文件
    if cat["doc"]:
        bullets.append("更新 {} 份文件（交接/說明）。".format(cat["doc"]))
    # 圖
    if cat["image"]:
        bullets.append("產生 {} 張圖（已隨信附上）。".format(cat["image"]))

    if not bullets:
        bullets.append("有檔案異動但無法判讀內容。")
    return bullets


# ---------------------------------------------------------------------------
def collect_images(groups):
    imgs = []
    for key, items in groups.items():
        for full, mt, sz, fn in items:
            if os.path.splitext(fn)[1].lower() in IMAGE_EXTS:
                imgs.append((key, full, mt, sz, fn))
    imgs.sort(key=lambda x: x[2], reverse=True)
    picked, total = [], 0
    for it in imgs:
        if len(picked) >= MAX_ATTACH:
            break
        if total + it[3] > MAX_TOTAL_MB * 1024 * 1024:
            continue
        picked.append(it)
        total += it[3]
    return imgs, picked


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
CSS = """
<style>
 body{font-family:"Microsoft JhengHei","Segoe UI",sans-serif;color:#222;font-size:14px;line-height:1.6}
 h1{font-size:20px;border-bottom:2px solid #2c6;padding-bottom:6px}
 h2{font-size:16px;margin-top:24px;background:#f0f4f0;padding:6px 10px;border-left:4px solid #2c6}
 ul{margin:8px 0 8px 4px;padding-left:22px}
 li{margin:4px 0}
 .meta{color:#666;font-size:13px}
</style>
"""


def build_html(since, now, groups, all_imgs, attached):
    p = ["<html><head><meta charset='utf-8'>" + CSS + "</head><body>"]
    p.append("<h1>FLAC3D 進度報告　{}</h1>".format(now.strftime("%Y-%m-%d %H:%M")))
    p.append("<p class='meta'>掃描範圍：{}<br>變動區間：{} ～ {}</p>".format(
        "、".join(SCAN_ROOTS),
        since.strftime("%Y-%m-%d %H:%M"), now.strftime("%Y-%m-%d %H:%M")))

    if not groups:
        p.append("<h2>本期無任何檔案變動</h2>")
        p.append("<p>這段期間 FLAC3D 可能沒在跑，或尚未產出新檔。</p></body></html>")
        return "\n".join(p)

    total_files = sum(len(v) for v in groups.values())
    p.append("<p><b>本期摘要：</b>{} 個資料夾有更新，共異動 {} 個檔，更新圖片 {} 張"
             "（隨信附上 {} 張）。</p>".format(
                 len(groups), total_files, len(all_imgs), len(attached)))

    for key in sorted(groups):
        p.append("<h2>📁 {}</h2>".format(key))
        p.append("<ul>")
        for b in summarize_group(groups[key]):
            p.append("<li>{}</li>".format(b))
        p.append("</ul>")

    p.append("</body></html>")
    return "\n".join(p)


# ---------------------------------------------------------------------------
def send_email(subject, html_body, attachments):
    if not os.path.exists(MAIL_CFG):
        print("[mail] no mail_config.json, skip")
        return False
    with open(MAIL_CFG, encoding="utf-8") as f:
        cfg = json.load(f)
    if not cfg.get("enabled"):
        print("[mail] disabled, skip")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["username"]
    msg["To"] = cfg["to"]
    msg.set_content("此信為 HTML 格式，請用支援 HTML 的郵件軟體檢視。")
    msg.add_alternative(html_body, subtype="html")

    for key, full, mt, sz, fn in attachments:
        try:
            ctype, _ = mimetypes.guess_type(full)
            maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
            with open(full, "rb") as fp:
                data = fp.read()
            aname = "{}_{}".format(key.replace("/", "_"), fn)
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=aname)
        except Exception as e:
            print("[mail] attach failed {}: {}".format(full, e))

    try:
        with smtplib.SMTP(cfg.get("smtp_host", "smtp.gmail.com"),
                          cfg.get("smtp_port", 587), timeout=60) as s:
            s.starttls()
            s.login(cfg["username"], cfg["app_password"])
            s.send_message(msg)
        print("[mail] sent to", cfg["to"])
        return True
    except Exception as e:
        print("[mail] send failed:", e)
        return False


# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    now = datetime.now()
    since = get_since()

    groups = scan_changes(since)
    all_imgs, attached = collect_images(groups)
    html = build_html(since, now, groups, all_imgs, attached)

    stamp = now.strftime("%Y-%m-%d_%H%M")
    html_path = os.path.join(OUT_DIR, "report_{}.html".format(stamp))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("[daily_report] wrote", html_path)

    n_changed = sum(len(v) for v in groups.values())
    subject = "FLAC3D 進度 {} — {} 資料夾 / {} 檔 / {} 圖".format(
        now.strftime("%m/%d"), len(groups), n_changed, len(all_imgs))
    send_email(subject, html, attached)

    save_state(now)


if __name__ == "__main__":
    main()
