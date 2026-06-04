# -*- coding: utf-8 -*-
"""Generate daily Codex schedule notes and an HTML report for FLAC_AI."""

import argparse
import csv
import html
import json
import os
import re
import subprocess
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from xml.etree import ElementTree


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEDULE_DIR = os.path.join(ROOT, "scripts", "codex_schedule")
REPORT_DIR = os.path.join(ROOT, "scripts", "codex_repeort")

DEFAULT_ROOTS = ["AI_交接", "3D_small", "mechanical_properties", "3D_far", "2D"]
ALLOWED_EXTS = {".py", ".ipyn", ".ipynb", ".dat", ".f3dat", ".md", ".txt", ".csv", ".xlsx", ".ps1", ".png"}
LOG_EXTS = {".log"}
EXCLUDE_DIRS = {".git", "__pycache__", ".ipynb_checkpoints", ".vscode", "codex_repeort"}
EXCLUDE_PREFIXES = {
    "output/codex_monitor/",
    "scripts/codex_repeort/",
}
MAX_FILE_LIST = 120
MAX_TEXT_BYTES = 160_000
MAX_CSV_BYTES = 50 * 1024 * 1024
MAX_COMMIT_BYTES = 95 * 1024 * 1024


def relpath(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def to_abs(path):
    return os.path.join(ROOT, path.replace("/", os.sep))


def is_excluded(rel):
    rel_norm = rel.replace("\\", "/")
    return any(rel_norm.startswith(prefix) for prefix in EXCLUDE_PREFIXES)


def read_text(path, max_bytes=MAX_TEXT_BYTES):
    try:
        with open(path, "rb") as f:
            raw = f.read(max_bytes + 1)
        truncated = len(raw) > max_bytes
        text = raw[:max_bytes].decode("utf-8-sig", errors="replace")
        return text, truncated
    except OSError as exc:
        return "READ_ERROR: {}".format(exc), False


def git_status_map():
    try:
        raw = subprocess.check_output(
            ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return {}

    parts = raw.split(b"\0")
    result = {}
    i = 0
    while i < len(parts):
        item = parts[i]
        if not item:
            i += 1
            continue
        text = item.decode("utf-8", errors="replace")
        code = text[:2]
        path = text[3:].replace("\\", "/")
        result[path] = code.strip() or "modified"
        if code.startswith("R") or code.startswith("C"):
            i += 1
        i += 1
    return result


def file_record(path, status_lookup):
    st = os.stat(path)
    rel = relpath(path)
    return {
        "path": rel,
        "root": rel.split("/", 1)[0],
        "ext": os.path.splitext(path)[1].lower(),
        "size_bytes": st.st_size,
        "size_mb": round(st.st_size / 1024 / 1024, 3),
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        "git_status": status_lookup.get(rel, "clean-or-already-tracked"),
        "commit_candidate": st.st_size <= MAX_COMMIT_BYTES,
    }


def scan_files(roots, since):
    since_ts = since.timestamp()
    records = []
    logs = []
    missing_roots = []
    status_lookup = git_status_map()

    for root_name in roots:
        root_dir = os.path.join(ROOT, root_name)
        if not os.path.isdir(root_dir):
            missing_roots.append(root_name)
            continue
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for filename in filenames:
                full = os.path.join(dirpath, filename)
                rel = relpath(full)
                if is_excluded(rel):
                    continue
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                if st.st_mtime < since_ts:
                    continue
                ext = os.path.splitext(filename)[1].lower()
                if ext in ALLOWED_EXTS:
                    records.append(file_record(full, status_lookup))
                elif ext in LOG_EXTS:
                    logs.append(file_record(full, status_lookup))

    records.sort(key=lambda x: (x["mtime"], x["path"]), reverse=True)
    logs.sort(key=lambda x: (x["mtime"], x["path"]), reverse=True)
    return records, logs, missing_roots


def previous_schedule_reports(today_name, limit=5):
    if not os.path.isdir(SCHEDULE_DIR):
        return []
    reports = []
    for name in os.listdir(SCHEDULE_DIR):
        if not name.lower().endswith(".md") or name == today_name:
            continue
        full = os.path.join(SCHEDULE_DIR, name)
        if not os.path.isfile(full):
            continue
        text, _ = read_text(full, 40_000)
        headings = [line.strip() for line in text.splitlines() if line.startswith("#")][:12]
        reports.append({
            "path": relpath(full),
            "mtime": datetime.fromtimestamp(os.path.getmtime(full)).isoformat(timespec="seconds"),
            "headings": headings,
        })
    reports.sort(key=lambda x: x["mtime"], reverse=True)
    return reports[:limit]


def summarize_text_file(path, ext):
    text, truncated = read_text(path)
    lines = text.splitlines()
    summary = {
        "kind": "text",
        "line_count_scanned": len(lines),
        "truncated": truncated,
    }
    if ext == ".md":
        summary["headings"] = [line.strip() for line in lines if line.lstrip().startswith("#")][:30]
        summary["bullets"] = [line.strip() for line in lines if line.strip().startswith("- ")][:30]
    elif ext == ".py":
        summary["imports"] = [line.strip() for line in lines if line.strip().startswith(("import ", "from "))][:30]
        summary["definitions"] = [
            line.strip()
            for line in lines
            if re.match(r"^\s*(def|class)\s+[A-Za-z_][A-Za-z0-9_]*", line)
        ][:40]
        summary["entrypoints"] = [line.strip() for line in lines if "__main__" in line][:10]
    elif ext in {".f3dat", ".dat", ".ps1", ".txt"}:
        keywords = (
            "model ", "program ", "fish define", "global ", "zone ", "structure ",
            "call ", "restore", "save", "solve", "excav", "liner", "shell",
            "csv", "monitor", "ratio", "cycle",
        )
        summary["key_lines"] = [
            line.strip()
            for line in lines
            if any(key in line.lower() for key in keywords)
        ][:60]
    return summary


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_csv(path):
    if os.path.getsize(path) > MAX_CSV_BYTES:
        return {"kind": "csv", "status": "skipped_large_csv"}
    try:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            rows = 0
            latest = None
            numeric = {}
            keys = ["step", "cycle", "ratio", "converged", "crown", "wall", "conv", "plastic", "disp"]
            interesting = [field for field in fields if any(key in field.lower() for key in keys)]
            for row in reader:
                if not row:
                    continue
                rows += 1
                latest = row
                for field in interesting[:40]:
                    value = safe_float(row.get(field))
                    if value is None:
                        continue
                    stats = numeric.setdefault(field, {"min": value, "max": value, "latest": value})
                    stats["min"] = min(stats["min"], value)
                    stats["max"] = max(stats["max"], value)
                    stats["latest"] = value
    except Exception as exc:
        return {"kind": "csv", "status": "read_error", "error": str(exc)}

    result = {
        "kind": "csv",
        "status": "empty" if rows == 0 else "ok",
        "rows": rows,
        "columns": fields[:80],
        "interesting_columns": interesting[:40],
        "numeric_stats": numeric,
    }
    if latest:
        result["latest"] = {field: latest.get(field, "") for field in interesting[:30]}
    return result


def summarize_png(path):
    result = {"kind": "png", "status": "ok"}
    try:
        with open(path, "rb") as f:
            header = f.read(24)
        if header.startswith(b"\x89PNG\r\n\x1a\n") and header[12:16] == b"IHDR":
            result["width"] = int.from_bytes(header[16:20], "big")
            result["height"] = int.from_bytes(header[20:24], "big")
        else:
            result["status"] = "not_png_header"
    except OSError as exc:
        result["status"] = "read_error"
        result["error"] = str(exc)
    return result


def summarize_ipynb(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            nb = json.load(f)
    except Exception as exc:
        return {"kind": "notebook", "status": "read_error", "error": str(exc)}
    cells = nb.get("cells", [])
    markdown_headings = []
    code_starts = []
    for cell in cells:
        source = cell.get("source", [])
        if isinstance(source, list):
            text = "".join(source)
        else:
            text = str(source)
        if cell.get("cell_type") == "markdown":
            markdown_headings.extend([line.strip() for line in text.splitlines() if line.startswith("#")])
        elif cell.get("cell_type") == "code":
            for line in text.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    code_starts.append(stripped)
                    break
    return {
        "kind": "notebook",
        "status": "ok",
        "cell_count": len(cells),
        "markdown_headings": markdown_headings[:20],
        "code_cell_starts": code_starts[:20],
    }


def summarize_xlsx(path):
    result = {"kind": "xlsx", "status": "ok", "sheets": []}
    try:
        with zipfile.ZipFile(path) as z:
            workbook = ElementTree.fromstring(z.read("xl/workbook.xml"))
            ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for sheet in workbook.findall(".//x:sheet", ns):
                result["sheets"].append(sheet.attrib.get("name", ""))
    except Exception as exc:
        result["status"] = "read_error"
        result["error"] = str(exc)
    return result


def summarize_file(record):
    path = to_abs(record["path"])
    ext = record["ext"]
    if ext == ".csv":
        return summarize_csv(path)
    if ext == ".png":
        return summarize_png(path)
    if ext in {".ipynb", ".ipyn"}:
        return summarize_ipynb(path)
    if ext == ".xlsx":
        return summarize_xlsx(path)
    if ext in {".py", ".dat", ".f3dat", ".md", ".txt", ".ps1"}:
        return summarize_text_file(path, ext)
    return {"kind": "unknown", "status": "not_summarized"}


def build_data(roots, hours):
    now = datetime.now()
    since = now - timedelta(hours=hours)
    today_name = "{}.md".format(now.strftime("%Y-%m-%d"))
    records, logs, missing_roots = scan_files(roots, since)

    counts = Counter((rec["root"], rec["ext"]) for rec in records)
    detailed = []
    for rec in records[:MAX_FILE_LIST]:
        item = dict(rec)
        item["summary"] = summarize_file(rec)
        detailed.append(item)

    return {
        "since": since.isoformat(timespec="seconds"),
        "until": now.isoformat(timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "roots": roots,
        "allowed_exts": sorted(ALLOWED_EXTS),
        "missing_roots": missing_roots,
        "counts": [
            {"root": root, "ext": ext, "count": count}
            for (root, ext), count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "records": records,
        "logs": logs,
        "detailed": detailed,
        "previous_reports": previous_schedule_reports(today_name),
        "oversized": [rec for rec in records if rec["size_bytes"] > MAX_COMMIT_BYTES],
        "commit_candidates": [rec for rec in records if rec["commit_candidate"]],
    }


def compact_value(value, max_len=180):
    text = str(value)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def build_markdown(data):
    lines = []
    lines.append("# {} 專案變動紀錄".format(data["date"]))
    lines.append("")
    lines.append("## 掃描範圍")
    lines.append("- 時間窗：{} 到 {}".format(data["since"], data["until"]))
    lines.append("- 根目錄：{}".format("、".join(data["roots"])))
    lines.append("- 允許提交副檔名：{}".format(", ".join(data["allowed_exts"])))
    lines.append("")

    if data["previous_reports"]:
        lines.append("## 前次 Schedule 參考")
        for report in data["previous_reports"]:
            lines.append("- {} ({})".format(report["path"], report["mtime"]))
            for heading in report["headings"][:6]:
                lines.append("  - {}".format(heading))
        lines.append("")

    lines.append("## 更動統計")
    if data["counts"]:
        for item in data["counts"]:
            lines.append("- {} {}：{} 個".format(item["root"], item["ext"], item["count"]))
    else:
        lines.append("- 最近 24 小時沒有符合白名單的檔案更動。")
    lines.append("")

    if data["missing_roots"]:
        lines.append("## 缺少的根目錄")
        for root in data["missing_roots"]:
            lines.append("- {}".format(root))
        lines.append("")

    lines.append("## 可提交候選檔案")
    for rec in data["commit_candidates"][:MAX_FILE_LIST]:
        lines.append("- {path} ({ext}, {size_mb} MB, {mtime}, git={git_status})".format(**rec))
    if len(data["commit_candidates"]) > MAX_FILE_LIST:
        lines.append("- ... 另有 {} 個候選檔案".format(len(data["commit_candidates"]) - MAX_FILE_LIST))
    if not data["commit_candidates"]:
        lines.append("- 無")
    lines.append("")

    lines.append("## 超過 95 MB 不提交")
    if data["oversized"]:
        for rec in data["oversized"]:
            lines.append("- {path} ({size_mb} MB)".format(**rec))
    else:
        lines.append("- 無")
    lines.append("")

    lines.append("## Log 檔只讀不提交")
    if data["logs"]:
        for rec in data["logs"][:40]:
            lines.append("- {path} ({size_mb} MB, {mtime})".format(**rec))
    else:
        lines.append("- 無")
    lines.append("")

    lines.append("## 詳細檔案內容摘要")
    if not data["detailed"]:
        lines.append("- 無符合條件的檔案可分析。")
    for item in data["detailed"]:
        lines.append("### {}".format(item["path"]))
        lines.append("- 類型：{}；大小：{} MB；修改時間：{}；git：{}".format(
            item["ext"], item["size_mb"], item["mtime"], item["git_status"]
        ))
        summary = item["summary"]
        lines.append("- 摘要類型：{}；狀態：{}".format(summary.get("kind"), summary.get("status", "ok")))
        if summary.get("headings"):
            lines.append("- Markdown 標題：{}".format(" | ".join(summary["headings"][:8])))
        if summary.get("bullets"):
            lines.append("- Markdown 條列：{}".format(" | ".join(summary["bullets"][:6])))
        if summary.get("definitions"):
            lines.append("- Python 定義：{}".format(" | ".join(summary["definitions"][:10])))
        if summary.get("imports"):
            lines.append("- Python imports：{}".format(" | ".join(summary["imports"][:8])))
        if summary.get("key_lines"):
            lines.append("- 關鍵行：{}".format(" | ".join(summary["key_lines"][:10])))
        if summary.get("rows") is not None:
            lines.append("- CSV rows：{}；欄位：{}".format(
                summary.get("rows"), ", ".join(summary.get("columns", [])[:12])
            ))
        if summary.get("interesting_columns"):
            lines.append("- 監測欄位：{}".format(", ".join(summary["interesting_columns"][:12])))
        if summary.get("latest"):
            latest = "; ".join("{}={}".format(k, compact_value(v, 40)) for k, v in list(summary["latest"].items())[:12])
            lines.append("- 最新列：{}".format(latest))
        if summary.get("numeric_stats"):
            stats = []
            for key, val in list(summary["numeric_stats"].items())[:12]:
                stats.append("{} min={} max={} latest={}".format(key, val["min"], val["max"], val["latest"]))
            lines.append("- 數值統計：{}".format(" | ".join(stats)))
        if summary.get("width") and summary.get("height"):
            lines.append("- PNG 尺寸：{} x {}".format(summary["width"], summary["height"]))
        if summary.get("sheets"):
            lines.append("- Excel sheets：{}".format(", ".join(summary["sheets"][:20])))
        if summary.get("cell_count") is not None:
            lines.append("- Notebook cells：{}".format(summary["cell_count"]))
        lines.append("")
    return "\n".join(lines)


def html_list(items):
    if not items:
        return "<p>無</p>"
    return "<ul>" + "".join("<li>{}</li>".format(html.escape(str(item))) for item in items) + "</ul>"


def build_html(data, markdown_path):
    rows = []
    for item in data["detailed"]:
        summary = item["summary"]
        details = []
        if summary.get("interesting_columns"):
            details.append("監測欄位：" + ", ".join(summary["interesting_columns"][:10]))
        if summary.get("latest"):
            details.append("最新列：" + "; ".join("{}={}".format(k, compact_value(v, 35)) for k, v in list(summary["latest"].items())[:8]))
        if summary.get("definitions"):
            details.append("Python 定義：" + " | ".join(summary["definitions"][:8]))
        if summary.get("key_lines"):
            details.append("關鍵行：" + " | ".join(summary["key_lines"][:8]))
        if summary.get("headings"):
            details.append("標題：" + " | ".join(summary["headings"][:8]))
        if summary.get("width") and summary.get("height"):
            details.append("PNG：{} x {}".format(summary["width"], summary["height"]))
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(item["path"]),
                html.escape(item["ext"]),
                html.escape(str(item["size_mb"])),
                html.escape(item["git_status"]),
                html.escape("；".join(details) if details else summary.get("status", "ok")),
            )
        )

    count_rows = [
        "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(item["root"]), html.escape(item["ext"]), item["count"]
        )
        for item in data["counts"]
    ]
    pngs = [item["path"] for item in data["records"] if item["ext"] == ".png"]
    csvs = [item for item in data["detailed"] if item["summary"].get("kind") == "csv"]
    csv_notes = []
    for item in csvs:
        summary = item["summary"]
        latest = summary.get("latest", {})
        csv_notes.append("{}：rows={}；{}".format(
            item["path"],
            summary.get("rows", ""),
            "; ".join("{}={}".format(k, compact_value(v, 30)) for k, v in list(latest.items())[:8]),
        ))

    return """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>{date} FLAC_AI 專案變動報告</title>
  <style>
    body {{ font-family: "Microsoft JhengHei", Arial, sans-serif; margin: 28px; line-height: 1.55; color: #222; }}
    h1, h2 {{ color: #19324d; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d7dde5; padding: 7px 9px; vertical-align: top; font-size: 13px; }}
    th {{ background: #eef3f8; text-align: left; }}
    code {{ background: #f4f4f4; padding: 1px 4px; border-radius: 3px; }}
    .note {{ background: #fff8e6; border-left: 4px solid #d49400; padding: 10px 12px; }}
  </style>
</head>
<body>
  <h1>{date} FLAC_AI 專案變動報告</h1>
  <p>掃描時間窗：<code>{since}</code> 到 <code>{until}</code></p>
  <p>根目錄：{roots}</p>
  <p>Markdown schedule：<code>{md}</code></p>

  <h2>更動統計</h2>
  <table><thead><tr><th>根目錄</th><th>副檔名</th><th>數量</th></tr></thead><tbody>{count_rows}</tbody></table>

  <h2>開挖監測 CSV 摘要</h2>
  {csv_notes}

  <h2>PNG 圖片</h2>
  {pngs}

  <h2>Log 檔只讀不提交</h2>
  {logs}

  <h2>詳細檔案分析</h2>
  <table><thead><tr><th>檔案</th><th>類型</th><th>MB</th><th>Git 狀態</th><th>摘要</th></tr></thead><tbody>{rows}</tbody></table>

  <div class="note">HTML 報告保留本機；Git 提交仍只依白名單副檔名處理。</div>
</body>
</html>
""".format(
        date=html.escape(data["date"]),
        since=html.escape(data["since"]),
        until=html.escape(data["until"]),
        roots=html.escape("、".join(data["roots"])),
        md=html.escape(markdown_path),
        count_rows="".join(count_rows) if count_rows else "<tr><td colspan='3'>無</td></tr>",
        csv_notes=html_list(csv_notes),
        pngs=html_list(pngs[:80]),
        logs=html_list(["{} ({} MB)".format(item["path"], item["size_mb"]) for item in data["logs"][:60]]),
        rows="".join(rows) if rows else "<tr><td colspan='5'>無</td></tr>",
    )


def write_outputs(data):
    os.makedirs(SCHEDULE_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)
    md_path = os.path.join(SCHEDULE_DIR, "{}.md".format(data["date"]))
    html_path = os.path.join(REPORT_DIR, "{}.html".format(data["date"]))

    markdown = build_markdown(data)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(data, relpath(md_path)))

    return md_path, html_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--roots", default=",".join(DEFAULT_ROOTS))
    args = parser.parse_args()

    roots = [item.strip() for item in args.roots.split(",") if item.strip()]
    data = build_data(roots, args.hours)
    md_path, html_path = write_outputs(data)
    print("schedule_md={}".format(md_path))
    print("html_report={}".format(html_path))
    print("changed_files={}".format(len(data["records"])))
    print("log_files_seen={}".format(len(data["logs"])))


if __name__ == "__main__":
    main()
